"""Weekly attendance analytics and CSV/JSON report generation."""
from __future__ import annotations

import csv
import io
import json
import os
from datetime import date, datetime, timedelta
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


def _scan_all(table):
    items, kwargs = [], {}
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            return items
        kwargs["ExclusiveStartKey"] = key


def _query_date(table, day):
    items, kwargs = [], {
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
            Subject="Attendance weekly job failed",
            Message=str(exc)[:3000],
        )


def handler(event, context):
    del context
    try:
        supplied_week = (event or {}).get("week")
        if supplied_week:
            year_text, week_text = supplied_week.split("-W", maxsplit=1)
            monday = date.fromisocalendar(int(year_text), int(week_text), 1)
        else:
            previous_week = datetime.now(IST).date() - timedelta(days=7)
            monday = date.fromisocalendar(
                previous_week.isocalendar().year,
                previous_week.isocalendar().week,
                1,
            )
        sunday = monday + timedelta(days=6)
        week_id = f"{monday.isocalendar().year}-W{monday.isocalendar().week:02d}"

        employees_table = _table("TABLE_EMPLOYEES")
        attendance_table = _table("TABLE_ATTENDANCE")
        config = _table("TABLE_CONFIG")
        settings = config.get_item(Key={"pk": "SETTINGS"}).get("Item", {})
        weekend_days = {int(value) for value in settings.get("weekend_days", [6, 7])}
        holidays = set()
        for offset in range(7):
            day = monday + timedelta(days=offset)
            if config.get_item(Key={"pk": f"HOLIDAY#{day.isoformat()}"}).get("Item"):
                holidays.add(day)
        working_dates = [
            monday + timedelta(days=offset)
            for offset in range(7)
            if (monday + timedelta(days=offset)).isoweekday() not in weekend_days
            and (monday + timedelta(days=offset)) not in holidays
        ]
        working_days = len(working_dates)

        employees = [row for row in _scan_all(employees_table) if row.get("active") is True]
        records_by_employee = {row["employee_id"]: [] for row in employees}
        for day in working_dates:
            for record in _query_date(attendance_table, day.isoformat()):
                if record["employee_id"] in records_by_employee:
                    records_by_employee[record["employee_id"]].append(record)

        summaries = []
        totals_present = totals_late = totals_absent = 0
        for employee in employees:
            records = records_by_employee[employee["employee_id"]]
            present_days = sum(row.get("status") in {"present", "late"} for row in records)
            late_days = sum(row.get("status") == "late" for row in records)
            absent_days = sum(row.get("status") == "absent" for row in records)
            totals_present += present_days
            totals_late += late_days
            totals_absent += absent_days
            divisor = working_days or 0
            summaries.append({
                "employee_id": employee["employee_id"],
                "name": employee.get("name", ""),
                "present_days": present_days,
                "late_days": late_days,
                "absent_days": absent_days,
                "present_pct": round(present_days / divisor * 100, 1) if divisor else 0.0,
                "late_pct": round(late_days / divisor * 100, 1) if divisor else 0.0,
                "absent_pct": round(absent_days / divisor * 100, 1) if divisor else 0.0,
            })

        denominator = working_days * len(employees)
        totals = {
            "present_pct": round(totals_present / denominator * 100, 1) if denominator else 0.0,
            "late_pct": round(totals_late / denominator * 100, 1) if denominator else 0.0,
            "absent_pct": round(totals_absent / denominator * 100, 1) if denominator else 0.0,
        }
        report = {
            "week": week_id,
            "from": monday.isoformat(),
            "to": sunday.isoformat(),
            "working_days": working_days,
            "generated_at": _now(),
            "employees": summaries,
            "totals": totals,
        }
        bucket = os.getenv("BUCKET_REPORTS")
        if not bucket:
            raise RuntimeError("Missing required environment variable: BUCKET_REPORTS")
        s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        prefix = f"reports/weekly/{week_id}"
        s3.put_object(
            Bucket=bucket,
            Key=f"{prefix}.json",
            Body=json.dumps(report, default=_json_default).encode("utf-8"),
            ContentType="application/json",
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "employee_id", "name", "present_days", "late_days", "absent_days",
            "present_pct", "late_pct", "absent_pct",
        ])
        for row in summaries:
            writer.writerow([row[key] for key in (
                "employee_id", "name", "present_days", "late_days", "absent_days",
                "present_pct", "late_pct", "absent_pct",
            )])
        s3.put_object(
            Bucket=bucket,
            Key=f"{prefix}.csv",
            Body=output.getvalue().encode("utf-8"),
            ContentType="text/csv",
        )
        return {"week": week_id, "working_days": working_days, "totals": totals}
    except Exception as exc:
        _publish_failure(exc)
        raise
