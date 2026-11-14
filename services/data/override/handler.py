"""Admin API for correcting an employee attendance record with an audit trail."""
from __future__ import annotations

import json
import re
from datetime import date
from uuid import uuid4

from botocore.exceptions import BotoCoreError

from services.data.common import dynamodb_table, error, iso_now, require_admin, response

EMPLOYEE_ID_RE = re.compile(r"^[A-Z0-9_-]{3,20}$")
ALLOWED_FIELDS = {"clock_in", "clock_out", "status"}


def handler(event, context):
    del context
    try:
        actor = require_admin(event)
    except PermissionError as exc:
        return error(403, "forbidden", str(exc))
    except ImportError:
        return error(503, "auth_unavailable", "Shared admin authentication is not deployed yet")

    try:
        data = json.loads(event.get("body") or "{}")
        if not isinstance(data, dict):
            raise TypeError("Request body must be a JSON object")
        employee_id = data.get("employee_id")
        day = data.get("date")
        reason = data.get("reason")
        if not isinstance(employee_id, str) or not EMPLOYEE_ID_RE.fullmatch(employee_id):
            raise ValueError("employee_id format is invalid")
        if not isinstance(day, str):
            raise TypeError("date must use YYYY-MM-DD format")
        date.fromisoformat(day)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A non-empty reason is required")
        changes = {key: data[key] for key in ALLOWED_FIELDS if key in data}
        if not changes:
            raise ValueError("Provide at least one attendance field to override")
        if "status" in changes and changes["status"] not in {"present", "late", "absent"}:
            raise ValueError("status must be present, late or absent")
        for key in ("clock_in", "clock_out"):
            if key in changes and changes[key] is not None:
                from datetime import datetime

                if not isinstance(changes[key], str):
                    raise ValueError(f"{key} must be an ISO 8601 timestamp")
                datetime.fromisoformat(changes[key])

        attendance = dynamodb_table("TABLE_ATTENDANCE")
        key = {"employee_id": employee_id, "date": day}
        old = attendance.get_item(Key=key).get("Item")
        if not old:
            return error(404, "not_found", "Attendance record was not found")

        names = {"#source": "source", "#updated_at": "updated_at", "#updated_by": "updated_by"}
        values = {":source": "admin", ":updated_at": iso_now(), ":updated_by": actor}
        assignments = ["#source = :source", "#updated_at = :updated_at", "#updated_by = :updated_by"]
        for index, (field, value) in enumerate(changes.items()):
            name_key, value_key = f"#field{index}", f":value{index}"
            names[name_key] = field
            values[value_key] = value
            assignments.append(f"{name_key} = {value_key}")
        result = attendance.update_item(
            Key=key,
            UpdateExpression="SET " + ", ".join(assignments),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(employee_id)",
            ReturnValues="ALL_NEW",
        )
        new = result["Attributes"]
        dynamodb_table("TABLE_AUDIT").put_item(
            Item={
                "audit_id": str(uuid4()),
                "actor": actor,
                "action": "override",
                "employee_id": employee_id,
                "date": day,
                "old": old,
                "new": new,
                "reason": reason.strip(),
                "at": iso_now(),
            }
        )
        return response(200, new)
    except (ValueError, TypeError) as exc:
        return error(400, "validation_error", str(exc))
    except (BotoCoreError, RuntimeError, KeyError):
        return error(500, "internal_error", "Unable to override attendance record")
