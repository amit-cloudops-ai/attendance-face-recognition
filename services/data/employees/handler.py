"""Admin employee CRUD with consent capture and audit events."""
import json
import logging
import os
import re
import uuid

import boto3
from attendance_common.auth import get_username, require_group
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist, parse_hhmm, to_iso
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
REGION = "ap-south-1"
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _tables():
    db = boto3.resource("dynamodb", region_name=REGION)
    return (
        db.Table(_required_env("TABLE_EMPLOYEES")),
        db.Table(_required_env("TABLE_AUDIT")),
    )


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict):
        raise ValueError("request body must be a JSON object")
    return value


def _public_employee(item: dict) -> dict:
    return {key: value for key, value in item.items() if key != "face_ids"}


def _audit(table, event, action, employee_id, old, new, reason, at):
    table.put_item(Item={
        "audit_id": str(uuid.uuid4()),
        "actor": get_username(event),
        "action": action,
        "employee_id": employee_id,
        "old": old,
        "new": new,
        "reason": reason,
        "at": at,
    })


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    path = event.get("pathParameters") or {}
    employee_id = path.get("employee_id")
    method = (
        (event.get("requestContext") or {}).get("http", {}).get("method")
        or event.get("httpMethod", "GET")
    ).upper()
    try:
        employees, audit = _tables()
        if method == "GET" and employee_id:
            if not _EMPLOYEE_ID.fullmatch(employee_id):
                return error(400, "invalid_employee_id", "A valid employee_id is required.")
            item = employees.get_item(
                Key={"employee_id": employee_id}, ConsistentRead=True
            ).get("Item")
            if not item:
                return error(404, "employee_not_found", "The employee was not found.")
            return ok(_public_employee(item))

        if method == "GET":
            items = []
            response = employees.scan()
            items.extend(response.get("Items", []))
            while response.get("LastEvaluatedKey"):
                response = employees.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                items.extend(response.get("Items", []))
            items.sort(key=lambda item: item["employee_id"])
            return ok({"items": [_public_employee(item) for item in items]})

        if method == "POST":
            body = _body(event)
            employee_id = body.get("employee_id")
            if not isinstance(employee_id, str) or not _EMPLOYEE_ID.fullmatch(employee_id):
                return error(400, "invalid_employee_id", "employee_id must match ^[A-Z0-9_-]{3,20}$.")
            if body.get("consent") is not True:
                return error(400, "consent_required", "Explicit employee consent is required.")
            required = ("name", "email", "department", "shift_start", "shift_end")
            if any(not isinstance(body.get(key), str) or not body[key].strip() for key in required):
                return error(400, "invalid_employee", "Name, email, department and shift times are required.")
            if not _EMAIL.fullmatch(body["email"].strip()):
                return error(400, "invalid_email", "A valid email address is required.")
            try:
                parse_hhmm(body["shift_start"])
                parse_hhmm(body["shift_end"])
            except ValueError:
                return error(400, "invalid_shift_time", "Shift times must use HH:MM in 24-hour time.")
            now = to_iso(now_ist())
            item = {
                "employee_id": employee_id,
                "name": body["name"].strip(),
                "email": body["email"].strip().lower(),
                "department": body["department"].strip(),
                "shift_start": body["shift_start"],
                "shift_end": body["shift_end"],
                "active": True,
                "face_ids": [],
                "photo_count": 0,
                "consent_at": now,
                "created_at": now,
                "updated_at": now,
            }
            try:
                employees.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(employee_id)",
                )
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    return error(409, "employee_exists", "An employee with this ID already exists.")
                raise
            _audit(
                audit, event, "employee_create", employee_id, {},
                {"active": True, "consent_at": now, "name": item["name"]},
                "Employee created after explicit consent.", now,
            )
            return ok(_public_employee(item), status=201)

        if method == "DELETE" and employee_id:
            if not _EMPLOYEE_ID.fullmatch(employee_id):
                return error(400, "invalid_employee_id", "A valid employee_id is required.")
            old = employees.get_item(
                Key={"employee_id": employee_id}, ConsistentRead=True
            ).get("Item")
            if not old:
                return error(404, "employee_not_found", "The employee was not found.")
            if old.get("active", False):
                now = to_iso(now_ist())
                try:
                    employees.update_item(
                        Key={"employee_id": employee_id},
                        UpdateExpression="SET active=:inactive, updated_at=:now",
                        ConditionExpression="active=:active",
                        ExpressionAttributeValues={
                            ":inactive": False, ":active": True, ":now": now
                        },
                    )
                except ClientError as exc:
                    if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                        raise
                    latest = employees.get_item(
                        Key={"employee_id": employee_id}, ConsistentRead=True
                    ).get("Item")
                    return ok(_public_employee(latest or old))
                new = {**old, "active": False, "updated_at": now}
                _audit(
                    audit, event, "employee_deactivate", employee_id,
                    {"active": True}, {"active": False},
                    "Employee deactivated by administrator.", now,
                )
                return ok(_public_employee(new))
            return ok(_public_employee(old))

        return error(405, "method_not_allowed", "The requested method is not supported.")
    except ValueError as exc:
        return error(400, "invalid_request", str(exc))
    except Exception as exc:
        LOGGER.error("Employee handler failed (%s)", type(exc).__name__)
        return error(500, "internal_error", "Unable to process the employee request.")
