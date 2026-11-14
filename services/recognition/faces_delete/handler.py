"""Delete an employee's Rekognition templates and audit the administrative action."""
import logging
import os
import re
import uuid

import boto3
from attendance_common.auth import get_username, require_group
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist

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
        employees = db.Table(_required_env("TABLE_EMPLOYEES"))
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        if not employee:
            return error(404, "employee_not_found", "The employee was not found.")
        face_ids = list(employee.get("face_ids", []))
        rekognition = boto3.client("rekognition", region_name=REGION)
        deleted = 0
        for offset in range(0, len(face_ids), 4_096):
            response = rekognition.delete_faces(
                CollectionId=_required_env("COLLECTION_ID"),
                FaceIds=face_ids[offset:offset + 4_096],
            )
            deleted += len(response.get("DeletedFaces", []))

        now = now_ist().isoformat(timespec="seconds")
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression="SET face_ids=:empty, photo_count=:zero, updated_at=:now",
            ConditionExpression="attribute_exists(employee_id)",
            ExpressionAttributeValues={":empty": [], ":zero": 0, ":now": now},
        )
        db.Table(_required_env("TABLE_AUDIT")).put_item(Item={
            "audit_id": str(uuid.uuid4()),
            "actor": get_username(event),
            "action": "faces_delete",
            "employee_id": employee_id,
            "old": {"face_ids": face_ids, "photo_count": int(employee.get("photo_count", 0))},
            "new": {"face_ids": [], "photo_count": 0},
            "reason": "Biometric face templates removed by an administrator.",
            "at": now,
        })
        return ok({"deleted": deleted})
    except Exception:
        LOGGER.exception("Unable to delete employee face templates")
        return error(500, "internal_error", "Unable to delete employee face templates.")
