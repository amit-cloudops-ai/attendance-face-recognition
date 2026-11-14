"""Admin API for reading and updating attendance thresholds."""
from __future__ import annotations

from uuid import uuid4

from botocore.exceptions import BotoCoreError

from services.data.common import dynamodb_table, error, iso_now, require_admin, response

DEFAULTS = {
    "face_match_threshold": 95,
    "min_brightness": 40,
    "min_sharpness": 40,
    "grace_minutes": 15,
    "debounce_minutes": 10,
    "weekend_days": [6, 7],
    "max_photos_per_employee": 5,
}
RANGES = {
    "face_match_threshold": (80, 99.9),
    "grace_minutes": (0, 120),
    "debounce_minutes": (1, 60),
}


def _audit(actor, old, new):
    dynamodb_table("TABLE_AUDIT").put_item(
        Item={
            "audit_id": str(uuid4()),
            "actor": actor,
            "action": "settings_update",
            "old": old,
            "new": new,
            "reason": "Settings updated through admin API",
            "at": iso_now(),
        }
    )


def _validate(updates):
    unknown = set(updates) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
    for key, bounds in RANGES.items():
        if key in updates:
            value = updates[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key} must be numeric")
            if not bounds[0] <= value <= bounds[1]:
                raise ValueError(f"{key} must be between {bounds[0]} and {bounds[1]}")
    if "weekend_days" in updates:
        days = updates["weekend_days"]
        if (
            not isinstance(days, list)
            or any(isinstance(day, bool) or not isinstance(day, int) or day not in range(1, 8) for day in days)
            or len(set(days)) != len(days)
        ):
            raise ValueError("weekend_days must be a unique non-empty list of ISO weekdays 1..7")


def handler(event, context):
    del context
    try:
        actor = require_admin(event)
    except PermissionError as exc:
        return error(403, "forbidden", str(exc))
    except ImportError:
        return error(503, "auth_unavailable", "Shared admin authentication is not deployed yet")

    try:
        table = dynamodb_table("TABLE_CONFIG")
        old = {**DEFAULTS, **table.get_item(Key={"pk": "SETTINGS"}).get("Item", {})}
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        if method == "GET":
            old.pop("pk", None)
            return response(200, old)
        if method != "PUT":
            return error(405, "method_not_allowed", "Only GET and PUT are supported")

        import json

        updates = json.loads(event.get("body") or "{}")
        if not isinstance(updates, dict) or not updates:
            raise ValueError("Provide at least one setting to update")
        _validate(updates)
        new = {**old, **updates}
        new["pk"] = "SETTINGS"
        table.put_item(Item=new)
        audit_old = {key: value for key, value in old.items() if key != "pk"}
        audit_new = {key: value for key, value in new.items() if key != "pk"}
        _audit(actor, audit_old, audit_new)
        audit_new.pop("pk", None)
        return response(200, audit_new)
    except ValueError as exc:
        return error(400, "validation_error", str(exc))
    except (BotoCoreError, RuntimeError, TypeError, KeyError):
        return error(500, "internal_error", "Unable to process settings request")
