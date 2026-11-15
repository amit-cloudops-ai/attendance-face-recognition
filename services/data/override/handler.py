"""Admin attendance override with a mandatory reason and audit record."""
import json
import logging
import os
import re
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

import boto3
from attendance_common.auth import get_username, require_group
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist, to_iso
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
IST = ZoneInfo("Asia/Kolkata")
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")
_STATUSES = {"present", "late", "absent"}


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict):
        raise TypeError("request body must be a JSON object")
    return value


def _date(value) -> str:
    if not isinstance(value, str):
        raise TypeError("date must use YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return value


def _timestamp(value, label: str, business_date: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{label} must be an ISO 8601 timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone offset")
    normalized = parsed.astimezone(IST)
    if normalized.date().isoformat() != business_date:
        raise ValueError(f"{label} must fall on the attendance date in Asia/Kolkata")
    return normalized.isoformat(timespec="seconds")


def _ddb_item(item: dict) -> dict:
    serializer = TypeSerializer()
    return {key: serializer.serialize(value) for key, value in item.items()}


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    try:
        body = _body(event)
        employee_id = body.get("employee_id")
        if not isinstance(employee_id, str) or not _EMPLOYEE_ID.fullmatch(employee_id):
            return error(400, "invalid_employee_id", "A valid employee_id is required.")
        day = _date(body.get("date"))
        reason = body.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
            return error(400, "reason_required", "A reason of 1 to 500 characters is required.")
        db = boto3.resource("dynamodb", region_name=_region())
        employees = db.Table(_required_env("TABLE_EMPLOYEES"))
        attendance = db.Table(_required_env("TABLE_ATTENDANCE"))
        audit = db.Table(_required_env("TABLE_AUDIT"))
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        if not employee:
            return error(404, "employee_not_found", "The employee was not found.")
        key = {"employee_id": employee_id, "date": day}
        old = attendance.get_item(Key=key, ConsistentRead=True).get("Item") or {}
        status = body.get("status", old.get("status", "present"))
        if status not in _STATUSES:
            return error(400, "invalid_status", "status must be present, late or absent.")
        if status == "absent":
            if body.get("clock_in") is not None or body.get("clock_out") is not None:
                return error(400, "invalid_absent_record", "Absent records cannot contain clock times.")
            clock_in = clock_out = None
        else:
            clock_in = _timestamp(body.get("clock_in", old.get("clock_in")), "clock_in", day)
            clock_out = _timestamp(body.get("clock_out", old.get("clock_out")), "clock_out", day)
            if not clock_in:
                return error(400, "clock_in_required", "Present and late records require clock_in.")
            if clock_out and datetime.fromisoformat(clock_out) < datetime.fromisoformat(clock_in):
                return error(400, "invalid_clock_order", "clock_out cannot be earlier than clock_in.")

        now = to_iso(now_ist())
        username = get_username(event)
        item = {
            "employee_id": employee_id,
            "date": day,
            "status": status,
            "source": "admin",
            "updated_at": now,
            "updated_by": username,
        }
        if clock_in:
            item["clock_in"] = clock_in
        if clock_out:
            item["clock_out"] = clock_out
        if status != "absent" and old.get("flags"):
            item["flags"] = old["flags"]
        audit_item = {
            "audit_id": str(uuid.uuid4()),
            "actor": username,
            "action": "override",
            "employee_id": employee_id,
            "date": day,
            "old": old,
            "new": item,
            "reason": reason.strip(),
            "at": now,
        }
        if not old:
            condition = "attribute_not_exists(employee_id)"
            condition_values = None
        elif "updated_at" in old:
            condition = "attribute_exists(employee_id) AND updated_at=:old_updated"
            condition_values = {":old_updated": serializer.serialize(old["updated_at"])}
        else:
            condition = "attribute_exists(employee_id) AND attribute_not_exists(updated_at)"
            condition_values = None
        put = {
            "TableName": attendance.name,
            "Item": _ddb_item(item),
            "ConditionExpression": condition,
        }
        if condition_values:
            put["ExpressionAttributeValues"] = condition_values
        try:
            attendance.meta.client.transact_write_items(TransactItems=[
                {"Put": put},
                {"Put": {"TableName": audit.name, "Item": _ddb_item(audit_item)}},
            ])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "TransactionCanceledException":
                return error(409, "attendance_changed", "Attendance changed concurrently. Reload and retry the override.")
            raise
        return ok(item)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return error(400, "invalid_request", str(exc))
    except Exception as exc:  # noqa: BLE001 - API boundary returns a sanitized 500 response
        LOGGER.error("Attendance override failed (%s)", type(exc).__name__)
        return error(500, "internal_error", "Unable to override the attendance record.")
