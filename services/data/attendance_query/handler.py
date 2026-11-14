"""Admin attendance query API with employee/date filters and opaque pagination."""
from __future__ import annotations

import base64
import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError

from services.data.common import dynamodb_table, error, require_admin, response

EMPLOYEE_ID_RE = re.compile(r"^[A-Z0-9_-]{3,20}$")
VALID_STATUSES = {"present", "late", "absent"}


def _encode_cursor(payload):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value):
    if not value:
        return {}
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if not isinstance(decoded, dict):
            raise TypeError("cursor must be a JSON object")
        return decoded
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is invalid") from exc


def _all_employee_names(table):
    names = {}
    kwargs = {}
    while True:
        page = table.scan(ProjectionExpression="employee_id, #name", ExpressionAttributeNames={"#name": "name"}, **kwargs)
        for item in page.get("Items", []):
            names[item["employee_id"]] = item.get("name", "")
        key = page.get("LastEvaluatedKey")
        if not key:
            break
        kwargs["ExclusiveStartKey"] = key
    return names


def _format_item(item, names):
    return {
        "employee_id": item["employee_id"],
        "name": names.get(item["employee_id"], ""),
        "date": item["date"],
        "clock_in": item.get("clock_in"),
        "clock_out": item.get("clock_out"),
        "status": item.get("status"),
        "flags": sorted(item.get("flags", [])),
        "source": item.get("source"),
    }


def handler(event, context):
    del context
    try:
        require_admin(event)
    except PermissionError as exc:
        return error(403, "forbidden", str(exc))
    except ImportError:
        return error(503, "auth_unavailable", "Shared admin authentication is not deployed yet")

    try:
        params = event.get("queryStringParameters") or {}
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        from_date = date.fromisoformat(params.get("from") or today.isoformat())
        to_date = date.fromisoformat(params.get("to") or from_date.isoformat())
        if to_date < from_date:
            raise ValueError("to must be on or after from")
        if (to_date - from_date).days > 92:
            raise ValueError("date range cannot exceed 93 days")

        employee_id = params.get("employee_id")
        if employee_id and not EMPLOYEE_ID_RE.fullmatch(employee_id):
            raise ValueError("employee_id format is invalid")
        status = params.get("status")
        if status and status not in VALID_STATUSES:
            raise ValueError("status must be present, late or absent")
        limit = int(params.get("limit", "50"))
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")

        cursor = _decode_cursor(params.get("cursor"))
        attendance = dynamodb_table("TABLE_ATTENDANCE")
        employees = dynamodb_table("TABLE_EMPLOYEES")
        names = _all_employee_names(employees)
        filter_expression = Attr("status").eq(status) if status else None
        items = []
        next_cursor = None

        if employee_id:
            kwargs = {
                "KeyConditionExpression": (
                    Key("employee_id").eq(employee_id)
                    & Key("date").between(from_date.isoformat(), to_date.isoformat())
                ),
                "Limit": max(limit, 1),
            }
            if filter_expression is not None:
                kwargs["FilterExpression"] = filter_expression
            if cursor.get("last_key"):
                kwargs["ExclusiveStartKey"] = cursor["last_key"]

            while True:
                kwargs["Limit"] = max(limit - len(items), 1)
                page = attendance.query(**kwargs)
                items.extend(page.get("Items", []))
                last_key = page.get("LastEvaluatedKey")
                if len(items) >= limit:
                    if last_key:
                        next_cursor = _encode_cursor({"last_key": last_key})
                    break
                if not last_key:
                    break
                kwargs["ExclusiveStartKey"] = last_key
        else:
            current = date.fromisoformat(cursor["date"]) if cursor.get("date") else from_date
            last_key = cursor.get("last_key")
            while current <= to_date and len(items) < limit:
                kwargs = {
                    "IndexName": "date-index",
                    "KeyConditionExpression": Key("date").eq(current.isoformat()),
                    "Limit": max(limit - len(items), 1),
                }
                if filter_expression is not None:
                    kwargs["FilterExpression"] = filter_expression
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                while True:
                    kwargs["Limit"] = max(limit - len(items), 1)
                    page = attendance.query(**kwargs)
                    items.extend(page.get("Items", []))
                    last_key = page.get("LastEvaluatedKey")
                    if len(items) >= limit:
                        if last_key:
                            next_cursor = _encode_cursor(
                                {"date": current.isoformat(), "last_key": last_key}
                            )
                        elif current < to_date:
                            next_cursor = _encode_cursor(
                                {"date": (current + timedelta(days=1)).isoformat()}
                            )
                        break
                    if not last_key:
                        break
                    kwargs["ExclusiveStartKey"] = last_key
                if len(items) >= limit:
                    break
                current += timedelta(days=1)
                last_key = None

        return response(
            200,
            {
                "items": [_format_item(item, names) for item in items[:limit]],
                "next_cursor": next_cursor,
            },
        )
    except (ValueError, TypeError) as exc:
        return error(400, "validation_error", str(exc))
    except (BotoCoreError, RuntimeError, KeyError, AttributeError):
        return error(500, "internal_error", "Unable to query attendance records")
