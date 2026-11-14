"""Atomic, request-idempotent DynamoDB attendance clock-in/clock-out transitions."""
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from .config import get_settings
from .tz import IST, parse_hhmm, to_iso

_MAX_ATTEMPTS = 5


def _table(env_name: str) -> Any:
    name = os.getenv(env_name)
    if not name:
        raise RuntimeError(f"required environment variable {env_name} is not set")
    return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1")).Table(name)


def _conditional_failure(exc: ClientError) -> bool:
    return exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _late_status(scanned_at: datetime, shift_start: str, grace_minutes: int) -> str:
    cutoff = datetime.combine(scanned_at.date(), parse_hhmm(shift_start), tzinfo=IST)
    return "late" if scanned_at > cutoff + timedelta(minutes=int(grace_minutes)) else "present"


def _result(action: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": action,
        "status": item["status"],
        "date": item["date"],
        "clock_in": item["clock_in"],
        "clock_out": item.get("clock_out"),
    }


def _remembered_result(item: dict[str, Any], request_id: str | None) -> dict[str, Any] | None:
    if request_id is None:
        return None
    events = item.get("scan_events") or {}
    remembered = events.get(request_id)
    if remembered is None:
        return None
    return remembered


def record_scan(
    employee_id: str,
    scanned_at: datetime,
    confidence: float,
    request_id: str | None = None,
) -> dict:
    """Persist one scan exactly once when request_id is supplied.

    The request outcome is stored atomically with the attendance transition. A
    retry after a successful attendance write therefore returns the original
    outcome instead of interpreting the same capture as a second scan.
    """
    if not isinstance(employee_id, str) or not employee_id:
        raise ValueError("employee_id is required")
    if scanned_at.tzinfo is None or scanned_at.utcoffset() is None:
        raise ValueError("scanned_at must be timezone-aware")
    if request_id is not None:
        try:
            parsed_request_id = UUID(request_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("request_id must be a UUID v4 string") from exc
        if parsed_request_id.version != 4:
            raise ValueError("request_id must be a UUID v4 string")

    confidence_value = float(confidence)
    if not 0 <= confidence_value <= 100:
        raise ValueError("confidence must be between 0 and 100")
    local_scan = scanned_at.astimezone(IST).replace(microsecond=0)
    scanned_iso, business_date = to_iso(local_scan), local_scan.date().isoformat()
    settings = get_settings()
    grace, debounce = int(settings["grace_minutes"]), int(settings["debounce_minutes"])
    if grace < 0 or debounce < 0:
        raise ValueError("grace_minutes and debounce_minutes cannot be negative")
    employees, attendance = _table("TABLE_EMPLOYEES"), _table("TABLE_ATTENDANCE")
    employee = employees.get_item(Key={"employee_id": employee_id}, ConsistentRead=True).get("Item")
    if not employee:
        raise ValueError(f"employee {employee_id} does not exist")
    if not employee.get("active", False):
        raise ValueError(f"employee {employee_id} is inactive")
    status = _late_status(local_scan, employee["shift_start"], grace)
    new_item = {
        "employee_id": employee_id,
        "date": business_date,
        "clock_in": scanned_iso,
        "status": status,
        "confidence": Decimal(str(confidence_value)),
        "source": "face",
        "updated_at": scanned_iso,
    }

    for _ in range(_MAX_ATTEMPTS):
        current = attendance.get_item(
            Key={"employee_id": employee_id, "date": business_date},
            ConsistentRead=True,
        ).get("Item")

        remembered = _remembered_result(current or {}, request_id)
        if remembered is not None:
            return remembered

        if current is None:
            outcome = _result("clock_in", new_item)
            item = dict(new_item)
            if request_id is not None:
                item["scan_events"] = {request_id: outcome}
            try:
                attendance.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(employee_id)",
                )
                return outcome
            except ClientError as exc:
                if _conditional_failure(exc):
                    continue
                raise

        if current.get("status") == "absent" and not current.get("clock_in"):
            outcome = _result("clock_in", {**current, **new_item})
            names = {"#st": "status", "#source": "source"}
            values = {
                ":ci": scanned_iso,
                ":st": status,
                ":cf": Decimal(str(confidence_value)),
                ":src": "face",
                ":ua": scanned_iso,
                ":absent": "absent",
            }
            update = (
                "SET clock_in=:ci, #st=:st, confidence=:cf, "
                "#source=:src, updated_at=:ua"
            )
            condition = "#st=:absent AND attribute_not_exists(clock_in)"
            if request_id is not None:
                names["#events"] = "scan_events"
                names["#request"] = request_id
                values[":outcome"] = outcome
                update += " , #events.#request=:outcome"
                condition += " AND attribute_not_exists(#events.#request)"
            try:
                attendance.update_item(
                    Key={"employee_id": employee_id, "date": business_date},
                    UpdateExpression=update + " REMOVE flags",
                    ConditionExpression=condition,
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues=values,
                )
                return outcome
            except ClientError as exc:
                if _conditional_failure(exc):
                    continue
                raise

        clock_in = datetime.fromisoformat(current["clock_in"]).astimezone(IST)
        old_out = current.get("clock_out")
        if local_scan < clock_in + timedelta(minutes=debounce):
            outcome = _result("duplicate_ignored", current)
            if request_id is None:
                return outcome
            try:
                attendance.update_item(
                    Key={"employee_id": employee_id, "date": business_date},
                    UpdateExpression="SET #events.#request=:outcome",
                    ConditionExpression="attribute_not_exists(#events.#request)",
                    ExpressionAttributeNames={"#events": "scan_events", "#request": request_id},
                    ExpressionAttributeValues={":outcome": outcome},
                )
                return outcome
            except ClientError as exc:
                if _conditional_failure(exc):
                    continue
                raise

        if old_out and local_scan <= datetime.fromisoformat(old_out).astimezone(IST):
            outcome = _result("clock_out", current)
            if request_id is None:
                return outcome
            try:
                attendance.update_item(
                    Key={"employee_id": employee_id, "date": business_date},
                    UpdateExpression="SET #events.#request=:outcome",
                    ConditionExpression="attribute_not_exists(#events.#request)",
                    ExpressionAttributeNames={"#events": "scan_events", "#request": request_id},
                    ExpressionAttributeValues={":outcome": outcome},
                )
                return outcome
            except ClientError as exc:
                if _conditional_failure(exc):
                    continue
                raise

        outcome_item = {**current, "clock_out": scanned_iso, "updated_at": scanned_iso}
        outcome = _result("clock_out", outcome_item)
        names = {}
        values = {
            ":ci": current["clock_in"],
            ":co": scanned_iso,
            ":ua": scanned_iso,
        }
        condition = "clock_in=:ci AND (attribute_not_exists(clock_out) OR clock_out < :co)"
        update = "SET clock_out=:co, updated_at=:ua"
        if request_id is not None:
            names = {"#events": "scan_events", "#request": request_id}
            values[":outcome"] = outcome
            condition += " AND attribute_not_exists(#events.#request)"
            update += ", #events.#request=:outcome"
        try:
            updated = attendance.update_item(
                Key={"employee_id": employee_id, "date": business_date},
                UpdateExpression=update,
                ConditionExpression=condition,
                ExpressionAttributeNames=names or None,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
            return _result("clock_out", updated["Attributes"])
        except ClientError as exc:
            if _conditional_failure(exc):
                continue
            raise
    raise RuntimeError("attendance record changed concurrently; retry the scan")
