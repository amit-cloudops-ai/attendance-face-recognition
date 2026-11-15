"""Filter and paginate attendance using the employee PK or date-index GSI."""
import base64
import json
import logging
import os
import re
from datetime import date, timedelta

import boto3
from attendance_common.auth import require_group
from attendance_common.responses import error, ok
from boto3.dynamodb.conditions import Attr, Key

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")
_STATUSES = {"present", "late", "absent"}


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _encode_cursor(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode())
        return decoded if isinstance(decoded, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


def _date_value(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return parsed


def _names(employees_table) -> dict:
    names = {}
    response = employees_table.scan(
        ProjectionExpression="employee_id,#name",
        ExpressionAttributeNames={"#name": "name"},
    )
    for item in response.get("Items", []):
        names[item["employee_id"]] = item.get("name", "")
    while response.get("LastEvaluatedKey"):
        response = employees_table.scan(
            ProjectionExpression="employee_id,#name",
            ExpressionAttributeNames={"#name": "name"},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        for item in response.get("Items", []):
            names[item["employee_id"]] = item.get("name", "")
    return names


def _valid_page_key(
    value: dict | None, *, date_text: str, employee_id: str | None = None
) -> bool:
    if not isinstance(value, dict) or set(value) != {"employee_id", "date"}:
        return False
    key_employee = value.get("employee_id")
    key_date = value.get("date")
    if not isinstance(key_employee, str) or not _EMPLOYEE_ID.fullmatch(key_employee):
        return False
    if employee_id is not None and key_employee != employee_id:
        return False
    try:
        parsed = _date_value(key_date)
    except (TypeError, ValueError):
        return False
    return parsed is not None and parsed.isoformat() == date_text


def _public_record(item: dict, names: dict) -> dict:
    flags = item.get("flags", [])
    if isinstance(flags, set):
        flags = sorted(flags)
    return {
        "employee_id": item["employee_id"],
        "name": names.get(item["employee_id"], ""),
        "date": item["date"],
        "clock_in": item.get("clock_in"),
        "clock_out": item.get("clock_out"),
        "status": item["status"],
        "flags": list(flags or []),
        "source": item.get("source"),
    }


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    params = event.get("queryStringParameters") or {}
    employee_id = params.get("employee_id")
    status = params.get("status")
    try:
        if employee_id and not _EMPLOYEE_ID.fullmatch(employee_id):
            return error(400, "invalid_employee_id", "A valid employee_id is required.")
        if status and status not in _STATUSES:
            return error(400, "invalid_status", "status must be present, late or absent.")
        start = _date_value(params.get("from"))
        end = _date_value(params.get("to"))
        if start and not end:
            end = start
        if end and not start:
            start = end
        if start and end and start > end:
            return error(400, "invalid_date_range", "from must be on or before to.")
        if start and end and (end - start).days > 365:
            return error(400, "date_range_too_large", "Date range cannot exceed 366 days.")
        if not employee_id and not start:
            return error(400, "filter_required", "Provide employee_id or a date filter.")
        try:
            limit = int(params.get("limit", "50"))
        except (TypeError, ValueError):
            return error(400, "invalid_limit", "limit must be an integer from 1 to 200.")
        if not 1 <= limit <= 200:
            return error(400, "invalid_limit", "limit must be an integer from 1 to 200.")

        cursor = _decode_cursor(params.get("cursor"))
        if params.get("cursor") and cursor is None:
            return error(400, "invalid_cursor", "cursor is invalid.")
        db = boto3.resource("dynamodb", region_name=_region())
        attendance = db.Table(_required_env("TABLE_ATTENDANCE"))
        employees = db.Table(_required_env("TABLE_EMPLOYEES"))
        filter_expression = Attr("status").eq(status) if status else None

        if employee_id:
            if cursor and (
                cursor.get("mode") != "employee"
                or not _valid_page_key(
                    cursor.get("last_key"),
                    date_text=cursor.get("last_key", {}).get("date")
                    if isinstance(cursor.get("last_key"), dict) else "",
                    employee_id=employee_id,
                )
                or (
                    start and _date_value(cursor["last_key"]["date"]) < start
                )
                or (
                    end and _date_value(cursor["last_key"]["date"]) > end
                )
            ):
                return error(400, "invalid_cursor", "cursor does not match the employee query.")
            kwargs = {
                "KeyConditionExpression": Key("employee_id").eq(employee_id),
                "Limit": limit,
            }
            if start and end:
                kwargs["KeyConditionExpression"] &= Key("date").between(
                    start.isoformat(), end.isoformat()
                )
            if filter_expression is not None:
                kwargs["FilterExpression"] = filter_expression
            if cursor:
                kwargs["ExclusiveStartKey"] = cursor["last_key"]
            response = attendance.query(**kwargs)
            items = response.get("Items", [])
            last_key = response.get("LastEvaluatedKey")
            next_cursor = _encode_cursor({"mode": "employee", "last_key": last_key}) if last_key else None
        else:
            current = cursor.get("date") if cursor else start.isoformat()
            last_key = cursor.get("last_key") if cursor else None
            if cursor and cursor.get("mode") != "date":
                return error(400, "invalid_cursor", "cursor does not match the date query.")
            try:
                cursor_date = _date_value(current)
            except ValueError:
                return error(400, "invalid_cursor", "cursor date is invalid.")
            if cursor_date is None or cursor_date < start or cursor_date > end:
                return error(400, "invalid_cursor", "cursor date is outside the requested range.")
            if last_key is not None and not _valid_page_key(
                last_key, date_text=current
            ):
                return error(400, "invalid_cursor", "cursor key is invalid for this date.");
            current = cursor_date.isoformat()
            items = []
            next_state = None
            while current and current <= end.isoformat() and len(items) < limit:
                kwargs = {
                    "IndexName": "date-index",
                    "KeyConditionExpression": Key("date").eq(current),
                    "Limit": max(1, limit - len(items)),
                }
                if filter_expression is not None:
                    kwargs["FilterExpression"] = filter_expression
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                response = attendance.query(**kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if last_key:
                    next_state = {"mode": "date", "date": current, "last_key": last_key}
                    if len(items) >= limit:
                        break
                    continue
                current = (date.fromisoformat(current) + timedelta(days=1)).isoformat()
                last_key = None
                next_state = (
                    {"mode": "date", "date": current, "last_key": None}
                    if current <= end.isoformat() else None
                )
                if len(items) >= limit:
                    break
            next_cursor = _encode_cursor(next_state) if next_state else None

        names = _names(employees)
        return ok({
            "items": [_public_record(item, names) for item in items],
            "next_cursor": next_cursor,
        })
    except ValueError as exc:
        return error(400, "invalid_query", str(exc))
    except Exception as exc:  # noqa: BLE001 - API boundary returns a sanitized 500 response
        LOGGER.error("Attendance query failed (%s)", type(exc).__name__)
        return error(500, "internal_error", "Unable to retrieve attendance records.")
