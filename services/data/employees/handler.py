"""Admin API for listing, creating, retrieving and deactivating employees."""
from __future__ import annotations

import re
from datetime import time
from uuid import uuid4

from botocore.exceptions import BotoCoreError

from services.data.common import dynamodb_table, error, iso_now, require_admin, response

EMPLOYEE_ID_RE = re.compile(r"^[A-Z0-9_-]{3,20}$")


def _audit(actor, action, employee_id, old, new):
    audit = dynamodb_table("TABLE_AUDIT")
    audit.put_item(
        Item={
            "audit_id": str(uuid4()),
            "actor": actor,
            "action": action,
            "employee_id": employee_id,
            "old": old or {},
            "new": new or {},
            "reason": f"{action.replace('_', ' ')} through admin API",
            "at": iso_now(),
        }
    )


def _validate_employee(data):
    if not isinstance(data, dict):
        raise TypeError("Request body must be a JSON object")
    required = ("employee_id", "name", "email", "department", "shift_start", "shift_end")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if not EMPLOYEE_ID_RE.fullmatch(data["employee_id"]):
        raise ValueError("employee_id must match ^[A-Z0-9_-]{3,20}$")
    for field in ("shift_start", "shift_end"):
        try:
            time.fromisoformat(data[field])
        except ValueError as exc:
            raise ValueError(f"{field} must use HH:MM format") from exc
        if len(data[field]) != 5:
            raise ValueError(f"{field} must use HH:MM format")
    if data.get("consent") is not True:
        raise ValueError("Explicit consent is required to create an employee")


def _all_employees(table):
    items = []
    kwargs = {}
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            break
        kwargs["ExclusiveStartKey"] = key
    return sorted(items, key=lambda item: item["employee_id"])


def handler(event, context):
    del context
    try:
        actor = require_admin(event)
    except PermissionError as exc:
        return error(403, "forbidden", str(exc))
    except ImportError:
        return error(503, "auth_unavailable", "Shared admin authentication is not deployed yet")

    table = dynamodb_table("TABLE_EMPLOYEES")
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    employee_id = event.get("pathParameters", {}).get("employee_id")

    try:
        if method == "GET" and not employee_id:
            return response(200, {"items": _all_employees(table)})

        if method == "GET" and employee_id:
            item = table.get_item(Key={"employee_id": employee_id}).get("Item")
            if not item:
                return error(404, "not_found", "Employee was not found")
            return response(200, item)

        if method == "POST":
            import json

            data = json.loads(event.get("body") or "{}")
            _validate_employee(data)
            created_at = iso_now()
            item = {
                "employee_id": data["employee_id"],
                "name": data["name"].strip(),
                "email": data["email"].strip(),
                "department": data["department"].strip(),
                "shift_start": data["shift_start"],
                "shift_end": data["shift_end"],
                "active": True,
                "face_ids": [],
                "photo_count": 0,
                "consent_at": created_at,
                "created_at": created_at,
                "updated_at": created_at,
            }
            try:
                table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(employee_id)",
                )
            except Exception as exc:
                if getattr(exc, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    return error(409, "already_exists", "Employee ID already exists")
                raise
            _audit(actor, "employee_create", item["employee_id"], {}, item)
            return response(201, item)

        if method == "DELETE" and employee_id:
            old = table.get_item(Key={"employee_id": employee_id}).get("Item")
            if not old:
                return error(404, "not_found", "Employee was not found")
            updated_at = iso_now()
            result = table.update_item(
                Key={"employee_id": employee_id},
                UpdateExpression="SET active = :inactive, updated_at = :updated",
                ConditionExpression="attribute_exists(employee_id)",
                ExpressionAttributeValues={":inactive": False, ":updated": updated_at},
                ReturnValues="ALL_NEW",
            )
            new = result["Attributes"]
            _audit(actor, "employee_deactivate", employee_id, old, new)
            return response(200, new)

        return error(405, "method_not_allowed", "Unsupported employee API operation")
    except (ValueError, TypeError) as exc:
        return error(400, "validation_error", str(exc))
    except (BotoCoreError, RuntimeError, KeyError):
        return error(500, "internal_error", "Unable to process employee request")
