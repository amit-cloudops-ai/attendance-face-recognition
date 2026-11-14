"""Return a minimal, contract-shaped scan result for kiosk polling."""
import logging
import os
import re

import boto3
from attendance_common.auth import require_group
from attendance_common.responses import error, ok

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
_REQUEST_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _authorized(event: dict) -> bool:
    return any(require_group(event, group) is None for group in ("kiosk", "admin"))


def lambda_handler(event, context):
    event = event or {}
    if not _authorized(event):
        return error(403, "forbidden", "A kiosk or admin account is required.")
    path = event.get("pathParameters") or {}
    request_id = path.get("request_id")
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        return error(400, "invalid_request_id", "A valid request_id is required.")
    try:
        table = boto3.resource(
            "dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1")
        ).Table(_required_env("TABLE_SCAN_RESULTS"))
        item = table.get_item(
            Key={"request_id": request_id}, ConsistentRead=True
        ).get("Item")
        if not item:
            return error(404, "not_found", "The scan request was not found.")
        body = {
            "request_id": request_id,
            "kind": item["kind"],
            "code": item["code"],
            "message": item.get("message", "Processing your request."),
        }
        for key in ("action", "name", "time", "status"):
            if key in item:
                body[key] = item[key]
        return ok(body)
    except Exception:
        LOGGER.exception("Unable to retrieve a scan result")
        return error(500, "internal_error", "Unable to retrieve the scan result.")
