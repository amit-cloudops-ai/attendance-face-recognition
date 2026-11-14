"""Atomic clock-in / clock-out logic shared by the recognition Lambda.

All attendance business dates are calculated in Asia/Kolkata. DynamoDB
conditional writes make the first scan safe when two recognition events race.
"""
from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_SETTINGS = {"grace_minutes": 15, "debounce_minutes": 10}


def _local_datetime(value: datetime) -> datetime:
    """Return an aware IST datetime; naive input is interpreted as IST."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(IST)


def _get_settings(config_table: Any) -> dict[str, Any]:
    """Use the Lead-owned cached settings helper when present, otherwise DynamoDB."""
    try:
        from attendance_common.config import get_settings  # type: ignore

        settings = get_settings()
        return {**DEFAULT_SETTINGS, **(settings or {})}
    except (ImportError, AttributeError):
        response = config_table.get_item(Key={"pk": "SETTINGS"})
        return {**DEFAULT_SETTINGS, **response.get("Item", {})}


def _is_conditional_failure(exc: Exception) -> bool:
    response = getattr(exc, "response", {})
    return response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _result(action: str, item: dict[str, Any], date: str) -> dict[str, Any]:
    return {
        "action": action,
        "status": item["status"],
        "date": date,
        "clock_in": item.get("clock_in"),
        "clock_out": item.get("clock_out"),
    }


def record_scan(
    employee_id: str,
    scanned_at: datetime,
    confidence: float,
) -> dict[str, Any]:
    """Record a recognized face as clock-in, clock-out, or ignored duplicate.

    Required environment variables are TABLE_EMPLOYEES, TABLE_ATTENDANCE and
    TABLE_CONFIG. AWS resources are created lazily to avoid import-time side effects.
    """
    import boto3

    if not employee_id:
        raise ValueError("employee_id is required")
    if not 0.0 <= float(confidence) <= 100.0:
        raise ValueError("confidence must be between 0 and 100")

    for variable in ("TABLE_EMPLOYEES", "TABLE_ATTENDANCE", "TABLE_CONFIG"):
        if not os.getenv(variable):
            raise RuntimeError(f"Missing required environment variable: {variable}")

    dynamodb = boto3.resource("dynamodb")
    employees = dynamodb.Table(os.environ["TABLE_EMPLOYEES"])
    attendance = dynamodb.Table(os.environ["TABLE_ATTENDANCE"])
    config = dynamodb.Table(os.environ["TABLE_CONFIG"])

    employee = employees.get_item(Key={"employee_id": employee_id}).get("Item")
    if not employee:
        raise ValueError(f"Unknown employee: {employee_id}")
    if not employee.get("active", True):
        raise ValueError(f"Inactive employee: {employee_id}")

    settings = _get_settings(config)
    grace_minutes = int(settings["grace_minutes"])
    debounce_minutes = int(settings["debounce_minutes"])
    if grace_minutes < 0 or debounce_minutes < 0:
        raise ValueError("Attendance timing settings cannot be negative")

    local_scan = _local_datetime(scanned_at)
    attendance_date = local_scan.date().isoformat()
    scanned_iso = local_scan.isoformat()
    shift_start = time.fromisoformat(employee["shift_start"])
    shift_start_at = datetime.combine(local_scan.date(), shift_start, tzinfo=IST)
    late_after = shift_start_at + timedelta(minutes=grace_minutes)
    status = "late" if local_scan > late_after else "present"

    item = {
        "employee_id": employee_id,
        "date": attendance_date,
        "clock_in": scanned_iso,
        "status": status,
        "source": "face",
        "confidence": Decimal(str(float(confidence))),
        "updated_at": scanned_iso,
    }

    try:
        attendance.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(employee_id)",
        )
        return _result("clock_in", item, attendance_date)
    except Exception as exc:
        if not _is_conditional_failure(exc):
            raise

    existing = attendance.get_item(
        Key={"employee_id": employee_id, "date": attendance_date},
        ConsistentRead=True,
    ).get("Item")
    if not existing:
        attendance.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(employee_id)",
        )
        return _result("clock_in", item, attendance_date)

    if existing.get("status") == "absent":
        try:
            converted = attendance.update_item(
                Key={"employee_id": employee_id, "date": attendance_date},
                UpdateExpression=(
                    "SET clock_in = :clock_in, #status = :status, "
                    "#source = :source, confidence = :confidence, updated_at = :updated_at"
                ),
                ConditionExpression="#status = :absent",
                ExpressionAttributeNames={"#status": "status", "#source": "source"},
                ExpressionAttributeValues={
                    ":clock_in": scanned_iso,
                    ":status": status,
                    ":source": "face",
                    ":confidence": Decimal(str(float(confidence))),
                    ":updated_at": scanned_iso,
                    ":absent": "absent",
                },
                ReturnValues="ALL_NEW",
            )
            return _result("clock_in", converted["Attributes"], attendance_date)
        except Exception as exc:
            if not _is_conditional_failure(exc):
                raise
            existing = attendance.get_item(
                Key={"employee_id": employee_id, "date": attendance_date},
                ConsistentRead=True,
            ).get("Item")
            if not existing:
                raise

    existing_clock_in = _local_datetime(datetime.fromisoformat(existing["clock_in"]))
    if local_scan - existing_clock_in < timedelta(minutes=debounce_minutes):
        return _result("duplicate_ignored", existing, attendance_date)

    updated = attendance.update_item(
        Key={"employee_id": employee_id, "date": attendance_date},
        UpdateExpression="SET clock_out = :clock_out, updated_at = :updated_at",
        ConditionExpression="attribute_exists(clock_in)",
        ExpressionAttributeValues={
            ":clock_out": scanned_iso,
            ":updated_at": scanned_iso,
        },
        ReturnValues="ALL_NEW",
    )
    return _result("clock_out", updated["Attributes"], attendance_date)
