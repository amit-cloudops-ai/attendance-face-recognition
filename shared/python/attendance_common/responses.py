"""API Gateway HTTP API proxy response helpers."""
import json
from typing import Any


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__float__"):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def ok(body: dict[str, Any], status: int = 200) -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "application/json; charset=utf-8"},
            "body": json.dumps(body, separators=(",", ":"), default=_json_default)}


def error(status: int, code: str, message: str) -> dict[str, Any]:
    return ok({"error": {"code": code, "message": message}}, status)
