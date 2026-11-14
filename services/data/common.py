"""Shared helpers for Part B Lambda handlers."""
from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def iso_now() -> str:
    return now_ist().isoformat()


def response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=json_default),
    }


def error(status: int, code: str, message: str) -> dict[str, Any]:
    return response(status, {"error": {"code": code, "message": message}})


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def body_json(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise TypeError("Request body must be a JSON object")
    return parsed


def require_admin(event: dict[str, Any]) -> str:
    """Fail closed until the Part C shared auth module is deployed."""
    from attendance_common.auth import get_username, require_group

    allowed = require_group(event, "admin")
    if allowed is False or (
        isinstance(allowed, dict) and int(allowed.get("statusCode", 200)) >= 400
    ):
        raise PermissionError("Admin access required")
    return str(get_username(event) or "unknown")


def dynamodb_table(env_name: str):
    import boto3

    table_name = os.getenv(env_name)
    if not table_name:
        raise RuntimeError(f"Missing required environment variable: {env_name}")
    return boto3.resource("dynamodb").Table(table_name)
