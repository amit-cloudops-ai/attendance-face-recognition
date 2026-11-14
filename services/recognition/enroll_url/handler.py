"""Create a constrained pre-signed POST for an employee enrollment photo."""
import logging
import os
import re
import time
import uuid

import boto3
from attendance_common.auth import require_group
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist, to_iso
from botocore.config import Config

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
REGION = "ap-south-1"
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    employee_id = (event.get("pathParameters") or {}).get("employee_id")
    if not isinstance(employee_id, str) or not _EMPLOYEE_ID.fullmatch(employee_id):
        return error(400, "invalid_employee_id", "A valid employee_id is required.")
    try:
        db = boto3.resource("dynamodb", region_name=REGION)
        employee = db.Table(_required_env("TABLE_EMPLOYEES")).get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        if not employee:
            return error(404, "employee_not_found", "The employee was not found.")
        if not employee.get("active", False):
            return error(409, "employee_inactive", "Inactive employees cannot be enrolled.")
        request_id = str(uuid.uuid4())
        created_at = to_iso(now_ist())
        db.Table(_required_env("TABLE_SCAN_RESULTS")).put_item(Item={
            "request_id": request_id, "kind": "enroll", "code": "pending",
            "message": "Enrollment photo uploaded. Processing is underway.",
            "created_at": created_at, "ttl": int(time.time()) + 86_400,
        })
        s3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4"))
        key = f"enroll/{employee_id}/{request_id}.jpg"
        upload = s3.generate_presigned_post(
            Bucket=_required_env("BUCKET_RAW"),
            Key=key,
            Fields={"Content-Type": "image/jpeg"},
            Conditions=[
                {"Content-Type": "image/jpeg"},
                ["content-length-range", 1_024, 1_048_576],
            ],
            ExpiresIn=60,
        )
        return ok({"request_id": request_id, "upload": upload, "expires_in": 60})
    except Exception:
        LOGGER.exception("Unable to create an enrollment upload request")
        return error(500, "internal_error", "Unable to prepare the enrollment upload.")
