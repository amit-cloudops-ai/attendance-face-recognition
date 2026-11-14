"""Daily attendance close-out, absence marking and report generation."""
from __future__ import annotations

import csv
import io
import json
import os
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key

IST = ZoneInfo("Asia/Kolkata")


def _now():
    return datetime.now(IST).isoformat()


def _table(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return boto3.resource("dynamodb").Table(value)


def _scan_all(table, **filters):
    items = []
    kwargs = dict(filters)
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            return items
        kwargs["ExclusiveStartKey"] = key


def _query_date(table, day):
    items = []
    kwargs = {
        "IndexName": "date-index",
        "KeyConditionExpression": Key("date").eq(day),
    }
    while True:
        page = table.query(**kwargs)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            return items
        kwargs["ExclusiveStartKey"] = key


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _publish_failure(exc):
    topic = os.getenv("SNS_TOPIC_ARN")
    if topic:
        boto3.client("sns", region_name=os.getenv("AWS_REGION", "ap-south-1")).publish(
            TopicArn=topic,
            Subject="Attendance daily job failed",
            Message=str(exc)[:3000],
        )


def handler(event, context):
    del context
    try:
        day = date.fromisoformat((event or {}).get("date") or datetime.now(IST).date().isoformat())
        day_text = day.isoformat()
        employees = _table("TABLE_EMPLOYEES")
        attendance = _table("TABLE_ATTENDANCE")
        config = _table("TABLE_CONFIG")
        settings = config.get_item(Key={"pk": "SETTINGS"}).get("Item", {})
        weekend_days = {int(value) for value in settings.get("weekend_days", [6, 7])}
        holiday = config.get_item(Key={"pk": f"HOLIDAY#{day_text}"}).get("Item")
        skipped = "holiday" if holiday else "weekend" if day.isoweekday() in weekend_days else None

        if skipped:
            report = {
                "date": day_text,
                "generated_at": _now(),
                "skipped": skipped,
                "totals": {
                    "employees": 0,
                    "present": 0,
                    "late": 0,
                    "absent": 0,
                    "missing_clock_out": 0,
                },
                "records": [],
            }
        else:
            active_employees = [
                item for item in _scan_all(employees) if item.get("active") is True
            ]
            for employee in active_employees:
                try:
                    attendance.put_item(
                        Item={
                            "employee_id": employee["employee_id"],
                            "date": day_text,
                            "status": "absent",
                            "source": "system",
                            "updated_at": _now(),
                        },
                        ConditionExpression="attribute_not_exists(employee_id)",
                    )
                except Exception as exc:
                    if getattr(exc, "response", {}).get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                        raise

            for record in _query_date(attendance, day_text):
                if record.get("clock_in") and not record.get("clock_out"):
                    try:
                        attendance.update_item(
                            Key={"employee_id": record["employee_id"], "date": day_text},
                            UpdateExpression="ADD #flags :flag",
                            ConditionExpression="attribute_exists(clock_in) AND attribute_not_exists(clock_out)",
                            ExpressionAttributeNames={"#flags": "flags"},
                            ExpressionAttributeValues={":flag": {"missing_clock_out"}},
                        )
                    except Exception as exc:
                        if getattr(exc, "response", {}).get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                            raise

            all_records = _query_date(attendance, day_text)
            employee_names = {
                item["employee_id"]: item.get("name", "")
                for item in active_employees
            }
            records = [
                {
                    "employee_id": row["employee_id"],
                    "name": employee_names.get(row["employee_id"], ""),
                    "status": row.get("status"),
                    "clock_in": row.get("clock_in"),
                    "clock_out": row.get("clock_out"),
                    "flags": sorted(row.get("flags", [])),
                }
                for row in all_records
            ]
            totals = {
                "employees": len(active_employees),
                "present": sum(row.get("status") == "present" for row in all_records),
                "late": sum(row.get("status") == "late" for row in all_records),
                "absent": sum(row.get("status") == "absent" for row in all_records),
                "missing_clock_out": sum(
                    "missing_clock_out" in row.get("flags", []) for row in all_records
                ),
            }
            report = {
                "date": day_text,
                "generated_at": _now(),
                "skipped": None,
                "totals": totals,
                "records": records,
            }

        bucket = os.getenv("BUCKET_REPORTS")
        if not bucket:
            raise RuntimeError("Missing required environment variable: BUCKET_REPORTS")
        s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        prefix = f"reports/daily/{day_text}"
        s3.put_object(
            Bucket=bucket,
            Key=f"{prefix}.json",
            Body=json.dumps(report, default=_json_default).encode("utf-8"),
            ContentType="application/json",
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["employee_id", "name", "date", "status", "clock_in", "clock_out", "flags"])
        for row in report["records"]:
            writer.writerow([
                row["employee_id"], row["name"], day_text, row["status"],
                row["clock_in"] or "", row["clock_out"] or ",".join(row["flags"]),
                ",".join(row["flags"]),
            ])
        s3.put_object(
            Bucket=bucket,
            Key=f"{prefix}.csv",
            Body=output.getvalue().encode("utf-8"),
            ContentType="text/csv",
        )
        return {"date": day_text, "skipped": skipped, "totals": report["totals"]}
    except Exception as exc:
        _publish_failure(exc)
        raise
