"""Previous-ISO-week attendance analytics and weekly JSON/CSV report generation."""
import csv
import io
import json
import logging
import os
import re
from datetime import date, timedelta

import boto3
from attendance_common.config import get_settings
from attendance_common.tz import now_ist, to_iso, today_ist
from boto3.dynamodb.conditions import Key

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
_WEEK = re.compile(r"^(\d{4})-W(\d{2})$")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _tables():
    db = boto3.resource("dynamodb", region_name=_region())
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


def _week_range(value):
    if value:
        match = _WEEK.fullmatch(value)
        if not match:
            raise ValueError("week must use YYYY-Www")
        try:
            monday = date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
        except ValueError as exc:
            raise ValueError("week is not a valid ISO week") from exc
        return value, monday, monday + timedelta(days=6)
    today = today_ist()
    this_monday = today - timedelta(days=today.isoweekday() - 1)
    monday = this_monday - timedelta(days=7)
    year, week, _ = monday.isocalendar()
    return f"{year}-W{week:02d}", monday, monday + timedelta(days=6)


def _attendance_for_employee(table, employee_id, start, end):
    items = []
    response = table.query(
        KeyConditionExpression=(
            Key("employee_id").eq(employee_id)
            & Key("date").between(start.isoformat(), end.isoformat())
        )
    )
    items.extend(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=(
                Key("employee_id").eq(employee_id)
                & Key("date").between(start.isoformat(), end.isoformat())
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _is_holiday(config, day):
    return config.get_item(Key={"pk": f"HOLIDAY#{day.isoformat()}"}).get("Item") is not None


def _alert_failure(exc):
    topic = os.getenv("ALERTS_TOPIC_ARN")
    if not topic:
        return
    try:
        boto3.client("sns", region_name=_region()).publish(
            TopicArn=topic,
            Subject="Attendance weekly job failed",
            Message=f"Weekly attendance job failed ({type(exc).__name__}). Check CloudWatch logs.",
        )
    except Exception:
        LOGGER.exception("Unable to publish weekly job failure alert")


def _write_report(s3, bucket, report):
    week = report["week"]
    s3.put_object(
        Bucket=bucket,
        Key=f"reports/weekly/{week}.json",
        Body=json.dumps(report, separators=(",", ":")).encode(),
        ContentType="application/json",
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "employee_id", "name", "present_days", "late_days", "absent_days",
        "present_pct", "late_pct", "absent_pct",
    ])
    for item in report["employees"]:
        writer.writerow([
            item["employee_id"], item["name"], item["present_days"], item["late_days"],
            item["absent_days"], item["present_pct"], item["late_pct"], item["absent_pct"],
        ])
    s3.put_object(
        Bucket=bucket,
        Key=f"reports/weekly/{week}.csv",
        Body=output.getvalue().encode(),
        ContentType="text/csv",
    )


def lambda_handler(event, context):
    event = event or {}
    try:
        week, start, end = _week_range(event.get("week"))
        employees_table, attendance_table, config_table = _tables()
        settings = get_settings()
        weekend_days = {int(value) for value in settings["weekend_days"]}
        working_dates = [
            day for offset in range(7)
            if (day := start + timedelta(days=offset)).isoweekday() not in weekend_days
            and not _is_holiday(config_table, day)
        ]
        working_days = len(working_dates)
        working_date_keys = {day.isoformat() for day in working_dates}
        active = _active_employees(employees_table)
        rows = []
        totals_present = totals_late = totals_absent = 0
        for employee in active:
            records = [
                record for record in _attendance_for_employee(
                    attendance_table, employee["employee_id"], start, end
                )
                if record.get("date") in working_date_keys
            ]
            present_days = sum(bool(record.get("clock_in")) for record in records)
            late_days = sum(record.get("status") == "late" for record in records)
            absent_days = sum(record.get("status") == "absent" for record in records)
            totals_present += present_days
            totals_late += late_days
            totals_absent += absent_days
            divisor = working_days or 1
            rows.append({
                "employee_id": employee["employee_id"],
                "name": employee.get("name", ""),
                "present_days": present_days,
                "late_days": late_days,
                "absent_days": absent_days,
                "present_pct": round(present_days / divisor * 100, 1) if working_days else 0.0,
                "late_pct": round(late_days / divisor * 100, 1) if working_days else 0.0,
                "absent_pct": round(absent_days / divisor * 100, 1) if working_days else 0.0,
            })
        denominator = working_days * len(active)
        totals = {
            "present_pct": round(totals_present / denominator * 100, 1) if denominator else 0.0,
            "late_pct": round(totals_late / denominator * 100, 1) if denominator else 0.0,
            "absent_pct": round(totals_absent / denominator * 100, 1) if denominator else 0.0,
        }
        report = {
            "week": week,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "working_days": working_days,
            "generated_at": to_iso(now_ist()),
            "employees": rows,
            "totals": totals,
        }
        _write_report(
            boto3.client("s3", region_name=_region()),
            _required_env("BUCKET_REPORTS"),
            report,
        )
        return {"statusCode": 200, "body": json.dumps({"week": week, "totals": totals})}
    except Exception as exc:
        LOGGER.error("Weekly job failed (%s)", type(exc).__name__)
        _alert_failure(exc)
        raise
