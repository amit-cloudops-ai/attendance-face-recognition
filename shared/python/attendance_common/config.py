"""DynamoDB-backed settings with documented defaults and a 60-second cache."""
import os
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

import boto3

DEFAULT_SETTINGS: dict[str, Any] = {
    "face_match_threshold": 95, "min_brightness": 40, "min_sharpness": 40,
    "grace_minutes": 15, "debounce_minutes": 10, "weekend_days": [6, 7],
    "max_photos_per_employee": 5,
}
_CACHE_SECONDS = 60
_lock = Lock()
_cache: dict[str, Any] | None = None
_cached_at: datetime | None = None


def _load() -> dict[str, Any]:
    table_name = os.getenv("TABLE_CONFIG")
    if not table_name:
        return DEFAULT_SETTINGS.copy()
    table = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")).Table(table_name)
    item = table.get_item(Key={"pk": "SETTINGS"}, ConsistentRead=True).get("Item", {})
    settings = DEFAULT_SETTINGS.copy()
    settings.update({key: value for key, value in item.items() if key in settings})
    return settings


def get_settings() -> dict[str, Any]:
    global _cache, _cached_at
    now = datetime.now(UTC)
    with _lock:
        if _cache is not None and _cached_at is not None and now - _cached_at < timedelta(seconds=_CACHE_SECONDS):
            return _cache.copy()
        _cache = _load()
        _cached_at = now
        return _cache.copy()


def _reset_cache() -> None:
    global _cache, _cached_at
    with _lock:
        _cache, _cached_at = None, None
