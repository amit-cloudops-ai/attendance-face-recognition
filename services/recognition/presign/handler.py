"""Create a short-lived, constrained S3 POST for a kiosk capture."""
import json
import logging
import os
import time
import uuid

import boto3
from botocore.config import Config

from attendance_common.auth import require_group
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist, to_iso

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
REGION = "ap-south-1"
MAX_IMAGE_BYTES = 1_048_576
MIN_IMAGE_BYTES = 1_024
POST_EXPIRY_SECONDS = 60


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _authorize(event: dict) -> dict | None:
    for group in ("kiosk", "admin"):
        response = require_group(event, group)
        if response is None:
            return None
    return error(403, "forbidden", "A kiosk or admin account is required.")


def lambda_handler(event, context):
    denied = _authorize(event or {})
    if denied:
        return denied
    try:
        request_id = str(uuid.uuid4())
        bucket = _required_env("BUCKET_RAW")
        table = boto3.resource("dynamodb", region_name=REGION).Table(
            _required_env("TABLE_SCAN_RESULTS")
        )
        created_at = to_iso(now_ist())
        table.put_item(Item={
            "request_id": request_id,
            "kind": "scan",
            "code": "pending",
            "message": "Capture uploaded. Recognition is processing.",
            "created_at": created_at,
            "ttl": int(time.time()) + 86_400,
        })
        s3 = boto3.client(
            "s3", region_name=REGION,
            config=Config(signature_version="s3v4"),
        )
        key = f"captures/{request_id}.jpg"
        upload = s3.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={"Content-Type": "image/jpeg"},
            Conditions=[
                {"Content-Type": "image/jpeg"},
                ["content-length-range", MIN_IMAGE_BYTES, MAX_IMAGE_BYTES],
            ],
            ExpiresIn=POST_EXPIRY_SECONDS,
        )
        return ok({
            "request_id": request_id,
            "upload": upload,
            "expires_in": POST_EXPIRY_SECONDS,
        })
    except Exception:
        LOGGER.exception("Unable to create a kiosk upload request")
        return error(500, "internal_error", "Unable to prepare the image upload. Please retry.")
