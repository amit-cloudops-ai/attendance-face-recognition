"""Delete an offboarded employee's Rekognition templates and audit the action."""
import hashlib
import logging
import os
import re

import boto3
from attendance_common.auth import get_username, require_group
from attendance_common.responses import error, ok
from attendance_common.tz import now_ist
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")
_NOT_FOUND_REASONS = {"FACE_NOT_FOUND", "RESOURCE_NOT_FOUND"}


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _audit_id(employee_id: str, face_ids: list[str]) -> str:
    fingerprint = hashlib.sha256(",".join(sorted(face_ids)).encode()).hexdigest()[:32]
    return f"faces-delete#{employee_id}#{fingerprint}"


def _delete_all_faces(rekognition, collection_id: str, face_ids: list[str]) -> int:
    confirmed = set()
    for offset in range(0, len(face_ids), 4_096):
        response = rekognition.delete_faces(
            CollectionId=collection_id,
            FaceIds=face_ids[offset:offset + 4_096],
        )
        confirmed.update(response.get("DeletedFaces", []))
        for failure in response.get("UnsuccessfulFaceDeletions", []):
            face_id = failure.get("FaceId")
            reason = failure.get("Reason")
            if reason in _NOT_FOUND_REASONS:
                confirmed.add(face_id)
            else:
                raise RuntimeError(
                    f"Rekognition could not delete a face template ({reason or 'unknown reason'})"
                )
    if confirmed != set(face_ids):
        raise RuntimeError("Rekognition did not confirm deletion of every face template")
    return len(confirmed)


def _ddb_item(item: dict) -> dict:
    serializer = TypeSerializer()
    return {key: serializer.serialize(value) for key, value in item.items()}


def lambda_handler(event, context):
    event = event or {}
    denied = require_group(event, "admin")
    if denied:
        return denied
    employee_id = (event.get("pathParameters") or {}).get("employee_id")
    if not isinstance(employee_id, str) or not _EMPLOYEE_ID.fullmatch(employee_id):
        return error(400, "invalid_employee_id", "A valid employee_id is required.")
    try:
        db = boto3.resource("dynamodb", region_name=_region())
        employees = db.Table(_required_env("TABLE_EMPLOYEES"))
        audit = db.Table(_required_env("TABLE_AUDIT"))
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        if not employee:
            return error(404, "employee_not_found", "The employee was not found.")
        if employee.get("active", False):
            return error(
                409, "employee_active",
                "Deactivate the employee before deleting biometric templates.",
            )

        face_ids = list(employee.get("face_ids", []))
        if not face_ids:
            return ok({"deleted": 0, "already_deleted": True})

        audit_id = _audit_id(employee_id, face_ids)
        now = now_ist().isoformat(timespec="seconds")
        deleted = _delete_all_faces(
            boto3.client("rekognition", region_name=_region()),
            _required_env("COLLECTION_ID"),
            face_ids,
        )

        audit_item = {
            "audit_id": audit_id,
            "actor": get_username(event),
            "action": "faces_delete",
            "employee_id": employee_id,
            "old": {
                "face_ids": face_ids,
                "photo_count": int(employee.get("photo_count", 0)),
            },
            "new": {"face_ids": [], "photo_count": 0},
            "reason": "Biometric face templates removed after employee deactivation.",
            "at": now,
        }
        values = {
            ":empty": [],
            ":zero": 0,
            ":now": now,
            ":audit_id": audit_id,
            ":inactive": False,
        }
        condition = "active=:inactive"
        if "updated_at" in employee:
            condition += " AND updated_at=:old_updated"
            values[":old_updated"] = employee["updated_at"]
        else:
            condition += " AND attribute_not_exists(updated_at)"
        try:
            employees.meta.client.transact_write_items(TransactItems=[
                {"Update": {
                    "TableName": employees.name,
                    "Key": _ddb_item({"employee_id": employee_id}),
                    "UpdateExpression": (
                        "SET face_ids=:empty, photo_count=:zero, updated_at=:now, "
                        "last_faces_delete_audit_id=:audit_id"
                    ),
                    "ConditionExpression": condition,
                    "ExpressionAttributeValues": _ddb_item(values),
                }},
                {"Put": {
                    "TableName": audit.name,
                    "Item": _ddb_item(audit_item),
                }},
            ])
        except ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code") != "TransactionCanceledException"
                or not any(
                    reason.get("Code") in {"ConditionalCheckFailed", "TransactionConflict"}
                    for reason in exc.response.get("CancellationReasons", [])
                )
            ):
                raise
            latest = employees.get_item(
                Key={"employee_id": employee_id}, ConsistentRead=True
            ).get("Item") or {}
            if latest.get("last_faces_delete_audit_id") == audit_id:
                return ok({"deleted": deleted, "already_deleted": True})
            return error(
                409, "employee_changed",
                "Employee state changed during offboarding. Reload and retry face deletion.",
            )

        return ok({"deleted": deleted})
    except Exception as exc:  # noqa: BLE001 - API boundary returns a sanitized response
        LOGGER.error("Face-template deletion failed (%s)", type(exc).__name__)
        return error(500, "internal_error", "Unable to delete all employee face templates.")
