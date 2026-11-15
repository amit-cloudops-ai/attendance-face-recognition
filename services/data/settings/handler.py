"""Admin GET/PUT endpoint for validated attendance configuration."""
import json
import logging
import os
import uuid

import boto3
from attendance_common.auth import get_username, require_group
from attendance_common.config import DEFAULT_SETTINGS, _reset_cache, get_settings
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist, to_iso
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")


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


def _validate_updates(body: dict) -> dict:
    unknown = set(body) - set(DEFAULT_SETTINGS)
    if unknown:
        raise ValueError(f"unsupported setting: {min(unknown)}")
    if not body:
        raise ValueError("provide at least one setting to update")
    validated = {}
    ranges = {
        "face_match_threshold": (50, 100),
        "min_brightness": (0, 100),
        "min_sharpness": (0, 100),
        "grace_minutes": (0, 180),
        "debounce_minutes": (1, 240),
        "max_photos_per_employee": (3, 5),
    }
    for key, (minimum, maximum) in ranges.items():
        if key not in body:
            continue
        value = body[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{key} must be an integer from {minimum} to {maximum}")
        validated[key] = value
    if "weekend_days" in body:
        days = body["weekend_days"]
        if (
            not isinstance(days, list)
            or any(isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 7 for day in days)
            or len(set(days)) != len(days)
        ):
            raise ValueError("weekend_days must be a unique list of ISO weekdays from 1 to 7")
        validated["weekend_days"] = sorted(days)
    return validated


def _ddb_item(item: dict) -> dict:
    serializer = TypeSerializer()
    return {key: serializer.serialize(value) for key, value in item.items()}


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    method = (
        (event.get("requestContext") or {}).get("http", {}).get("method")
        or event.get("httpMethod", "GET")
    ).upper()
    try:
        if method == "GET":
            return ok(get_settings())
        if method != "PUT":
            return error(405, "method_not_allowed", "Only GET and PUT are supported.")
        updates = _validate_updates(_body(event))
        db = boto3.resource("dynamodb", region_name=_region())
        config = db.Table(_required_env("TABLE_CONFIG"))
        audit = db.Table(_required_env("TABLE_AUDIT"))
        stored = config.get_item(
            Key={"pk": "SETTINGS"}, ConsistentRead=True
        ).get("Item")
        old = DEFAULT_SETTINGS.copy()
        if stored:
            old.update({key: value for key, value in stored.items() if key in DEFAULT_SETTINGS})
        new = {**old, **updates}
        now = to_iso(now_ist())
        username = get_username(event)
        config_item = {
            "pk": "SETTINGS",
            **new,
            "updated_at": now,
            "updated_by": username,
        }
        audit_item = {
            "audit_id": str(uuid.uuid4()),
            "actor": username,
            "action": "settings_update",
            "old": old,
            "new": new,
            "reason": "Attendance settings updated by administrator.",
            "at": now,
        }
        if stored and "updated_at" in stored:
            condition = "attribute_exists(pk) AND updated_at=:old_updated"
            condition_values = {":old_updated": serializer.serialize(stored["updated_at"])}
        elif stored:
            condition = "attribute_exists(pk) AND attribute_not_exists(updated_at)"
            condition_values = None
        else:
            condition = "attribute_not_exists(pk)"
            condition_values = None
        put_config = {
            "TableName": config.name,
            "Item": _ddb_item(config_item),
            "ConditionExpression": condition,
        }
        if condition_values:
            put_config["ExpressionAttributeValues"] = condition_values
        try:
            config.meta.client.transact_write_items(TransactItems=[
                {"Put": put_config},
                {"Put": {"TableName": audit.name, "Item": _ddb_item(audit_item)}},
            ])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "TransactionCanceledException":
                return error(409, "settings_changed", "Settings changed concurrently. Reload and retry the update.")
            raise
        _reset_cache()
        return ok(get_settings())
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return error(400, "invalid_settings", str(exc))
    except Exception as exc:  # noqa: BLE001 - API boundary returns a sanitized 500 response
        LOGGER.error("Settings handler failed (%s)", type(exc).__name__)
        return error(500, "internal_error", "Unable to process attendance settings.")
