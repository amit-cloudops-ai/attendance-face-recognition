"""IST daily attendance finalization and daily JSON/CSV report generation."""
import csv
import io
import json
import logging
import os
from datetime import date

import boto3
from attendance_common.config import get_settings
from attendance_common.tz import now_ist, today_ist, to_iso
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
REGION = "ap-south-1"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _tables():
    db = boto3.resource("dynamodb", region_name=REGION)
    return (
        db.Table(_required_env("TABLE_EMPLOYEES")),
        db.Table(_required_env("TABLE_ATTENDANCE")),
        db.Table(_required_env("TABLE_CONFIG")),
    )


def _active_employees(table):
    items = []
    response = table.scan()
    items.extend(item for item in response.get("Items", []) if item.get("active", False))
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(item for item in response.get("Items", []) if item.get("active", False))
    return sorted(items, key=lambda item: item["employee_id"])


def _attendance_for_date(table, date_text):
    items = []
    response = table.query(
        IndexName="date-index",
        KeyConditionExpression=Key("date").eq(date_text),
    )
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.query(
            IndexName="date-index",
            KeyConditionExpression=Key("date").eq(date_text),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return {item["employee_id"]: item for item in items}


def _is_holiday(config, date_text):
    return config.get_item(Key={"pk": f"HOLIDAY#{date_text}"}).get("Item")


def _alert_failure(exc):
    topic = os.getenv("ALERTS_TOPIC_ARN")
    if not topic:
        return
    try:
        boto3.client("sns", region_name=REGION).publish(
            TopicArn=topic,
            Subject="Attendance daily job failed",
            Message=f"Daily attendance job failed ({type(exc).__name__}). Check CloudWatch logs.",
        )
    except Exception:  # noqa: BLE001 - failure alerts must never mask the original job error
        LOGGER.exception("Unable to publish daily job failure alert")


def _write_report(s3, bucket, report):
    date_text = report["date"]
    json_key = f"reports/daily/{date_text}.json"
    csv_key = f"reports/daily/{date_text}.csv"
    s3.put_object(
        Bucket=bucket,
        Key=json_key,
        Body=json.dumps(report, separators=(",", ":")).encode(),
        ContentType="application/json",
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["employee_id", "name", "date", "status", "clock_in", "clock_out", "flags"])
    for item in report["records"]:
        writer.writerow([
            item["employee_id"], item["name"], date_text, item["status"],
            item["clock_in"] or "", item["clock_out"] or "", ";".join(item["flags"]),
        ])
    s3.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=output.getvalue().encode(),
        ContentType="text/csv",
    )


def lambda_handler(event, context):
    event = event or {}
    try:
        raw_date = event.get("date")
        day = date.fromisoformat(raw_date) if raw_date else today_ist()
        date_text = day.isoformat()
        employees_table, attendance_table, config_table = _tables()
        settings = get_settings()
        active = _active_employees(employees_table)
        weekend_days = {int(value) for value in settings["weekend_days"]}
        skipped = None
        if day.isoweekday() in weekend_days:
            skipped = "weekend"
        elif _is_holiday(config_table, date_text):
            skipped = "holiday"

        existing = {}
        now = to_iso(now_ist())
        if skipped is None:
            existing = _attendance_for_date(attendance_table, date_text)
            for employee in active:
                employee_id = employee["employee_id"]
                record = existing.get(employee_id)
                if record is None:
                    try:
                        attendance_table.put_item(
                            Item={
                                "employee_id": employee_id,
                                "date": date_text,
                                "status": "absent",
                                "source": "system",
                                "updated_at": now,
                            },
                            ConditionExpression="attribute_not_exists(employee_id)",
                        )
                    except ClientError as exc:
                        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                            raise
                elif record.get("clock_in") and not record.get("clock_out"):
                    try:
                        attendance_table.update_item(
                            Key={"employee_id": employee_id, "date": date_text},
                            UpdateExpression="SET updated_at=:now ADD flags :flags",
                            ConditionExpression="attribute_exists(clock_in) AND attribute_not_exists(clock_out)",
                            ExpressionAttributeValues={
                                ":now": now,
                                ":flags": {"missing_clock_out"},
                            },
                        )
                    except ClientError as exc:
                        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                            raise
            existing = _attendance_for_date(attendance_table, date_text)

        records = []
        for employee in active:
            row = existing.get(employee["employee_id"])
            if row is None:
                continue
            flags = row.get("flags", [])
            if isinstance(flags, set):
                flags = sorted(flags)
            records.append({
                "employee_id": employee["employee_id"],
                "name": employee.get("name", ""),
                "status": row.get("status", "absent"),
                "clock_in": row.get("clock_in"),
                "clock_out": row.get("clock_out"),
                "flags": list(flags or []),
            })

        totals = {
            "employees": len(active),
            "present": sum(row["status"] == "present" for row in records),
            "late": sum(row["status"] == "late" for row in records),
            "absent": sum(row["status"] == "absent" for row in records),
            "missing_clock_out": sum("missing_clock_out" in row["flags"] for row in records),
        }
        report = {
            "date": date_text,
            "generated_at": to_iso(now_ist()),
            "skipped": skipped,
            "totals": totals,
            "records": records,
        }
        _write_report(
            boto3.client("s3", region_name=REGION),
            _required_env("BUCKET_REPORTS"),
            report,
        )
        return {"statusCode": 200, "body": json.dumps({"date": date_text, "totals": totals})}
    except Exception as exc:  # noqa: BLE001 - scheduled job boundary alerts and re-raises failures
        LOGGER.error("Daily job failed (%s)", type(exc).__name__)
        _alert_failure(exc)
        raise
