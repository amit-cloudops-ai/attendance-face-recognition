"""Retry-safe S3 enrollment worker with idempotent employee updates."""
import logging
import os
import re
import time
from urllib.parse import unquote_plus
from uuid import UUID

import boto3
from attendance_common.config import get_settings
from attendance_common.tz import now_ist
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
_LOCK_SECONDS = 45


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _table(env_name: str):
    return boto3.resource("dynamodb", region_name=_region()).Table(_required_env(env_name))


def _not_found(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code")
    return code in {"NoSuchKey", "NotFound", "404"} or exc.response.get(
        "ResponseMetadata", {}
    ).get("HTTPStatusCode") == 404


def _parse_key(key: str) -> tuple[str, str] | None:
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "enroll" or not parts[2].endswith(".jpg"):
        return None
    employee_id, request_id = parts[1], parts[2][:-4]
    if not _EMPLOYEE_ID.fullmatch(employee_id):
        return None
    try:
        parsed = UUID(request_id)
    except ValueError:
        return None
    return (employee_id, request_id) if parsed.version == 4 else None


def _update_result(table, request_id: str, code: str, message: str, **fields) -> bool:
    names = {"#code": "code", "#message": "message"}
    values = {":code": code, ":message": message, ":pending": "pending"}
    assignments = ["#code=:code", "#message=:message"]
    for index, (key, value) in enumerate(fields.items()):
        name, token = f"#field{index}", f":value{index}"
        names[name], values[token] = key, value
        assignments.append(f"{name}={token}")
    try:
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET " + ", ".join(assignments),
            ConditionExpression="#code=:pending",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def _finish(s3, bucket: str, key: str, results, request_id: str, code: str,
            message: str, **fields) -> None:
    _update_result(results, request_id, code, message, **fields)
    # Delete only after a durable terminal result. Repeated deletion is safe.
    s3.delete_object(Bucket=bucket, Key=key)


def _external_employee_id(value: str) -> str:
    """Return the employee prefix from current or legacy Rekognition IDs."""
    # Employee IDs cannot contain either delimiter. Accept legacy "#" values
    # for compatibility, but only create new IDs with Rekognition-safe ":".
    return re.split(r"[#:]", value, maxsplit=1)[0]


def _request_marker(request_id: str) -> str:
    return f"enrollment_{request_id}"


def _acquire_employee_lock(employees, employee_id: str, request_id: str) -> None:
    now = int(time.time())
    try:
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression="SET enrollment_lock_request=:request, enrollment_lock_until=:until",
            ConditionExpression=(
                "active=:active AND "
                "(attribute_not_exists(enrollment_lock_until) OR enrollment_lock_until < :now)"
            ),
            ExpressionAttributeValues={
                ":active": True,
                ":request": request_id,
                ":until": now + _LOCK_SECONDS,
                ":now": now,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise RuntimeError("another enrollment is currently processing for this employee") from exc
        raise


def _release_employee_lock(employees, employee_id: str, request_id: str) -> None:
    try:
        employees.update_item(
            Key={"employee_id": employee_id},
            UpdateExpression="REMOVE enrollment_lock_request, enrollment_lock_until",
            ConditionExpression="enrollment_lock_request=:request",
            ExpressionAttributeValues={":request": request_id},
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise





def _delete_face_ids(rekognition, face_ids: list[str]) -> None:
    if not face_ids:
        return
    response = rekognition.delete_faces(
        CollectionId=_required_env("COLLECTION_ID"),
        FaceIds=face_ids,
    )
    confirmed = set(response.get("DeletedFaces", []))
    for failure in response.get("UnsuccessfulFaceDeletions", []):
        if failure.get("Reason") in {"FACE_NOT_FOUND", "RESOURCE_NOT_FOUND"}:
            confirmed.add(failure.get("FaceId"))
        else:
            raise RuntimeError("Rekognition could not remove an uncommitted enrollment face")
    if confirmed != set(face_ids):
        raise RuntimeError("Rekognition did not confirm cleanup of every uncommitted face")


def _delete_request_faces(rekognition, image: dict, external_id: str) -> None:
    matches = rekognition.search_faces_by_image(
        CollectionId=_required_env("COLLECTION_ID"),
        Image=image,
        FaceMatchThreshold=0.0,
        MaxFaces=10,
        QualityFilter="NONE",
    ).get("FaceMatches", [])
    face_ids = [
        (match.get("Face") or {}).get("FaceId")
        for match in matches
        if (match.get("Face") or {}).get("ExternalImageId") == external_id
        and (match.get("Face") or {}).get("FaceId")
    ]
    _delete_face_ids(rekognition, face_ids)


def _process_record(record: dict) -> None:
    info = record.get("s3") or {}
    bucket = (info.get("bucket") or {}).get("name")
    encoded_key = (info.get("object") or {}).get("key")
    if not bucket or not encoded_key:
        return
    key = unquote_plus(encoded_key)
    parsed = _parse_key(key)
    if not parsed:
        return
    employee_id, request_id = parsed
    s3 = boto3.client("s3", region_name=_region())
    results = _table("TABLE_SCAN_RESULTS")
    pending = results.get_item(
        Key={"request_id": request_id}, ConsistentRead=True
    ).get("Item")
    if not pending or pending.get("code") != "pending":
        s3.delete_object(Bucket=bucket, Key=key)
        return

    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if _not_found(exc):
            _finish(s3, bucket, key, results, request_id, "error",
                    "The uploaded enrollment image is no longer available.")
            return
        raise

    employees = _table("TABLE_EMPLOYEES")
    rekognition = boto3.client("rekognition", region_name=_region())
    image = {"S3Object": {"Bucket": bucket, "Name": key}}
    request_external_id = f"{employee_id}:{request_id}"
    marker = _request_marker(request_id)
    employee = employees.get_item(
        Key={"employee_id": employee_id}, ConsistentRead=True
    ).get("Item")

    if employee and employee.get(marker):
        _finish(s3, bucket, key, results, request_id, "enrolled",
                "Employee photo enrolled successfully.",
                employee_id=employee_id, name=employee.get("name", ""))
        return
    if not employee:
        _delete_request_faces(rekognition, image, request_external_id)
        _finish(s3, bucket, key, results, request_id, "unknown_employee",
                "The employee does not exist or is inactive.")
        return
    if not employee.get("active", False):
        _delete_request_faces(rekognition, image, request_external_id)
        _finish(s3, bucket, key, results, request_id, "unknown_employee",
                "The employee does not exist or is inactive.")
        return

    settings = get_settings()
    if int(employee.get("photo_count", 0)) >= int(settings["max_photos_per_employee"]):
        _delete_request_faces(rekognition, image, request_external_id)
        _finish(s3, bucket, key, results, request_id, "limit_reached",
                "The maximum number of enrollment photos has been reached.")
        return

    _acquire_employee_lock(employees, employee_id, request_id)
    indexed_face_ids = []
    try:
        # Refresh after acquiring the lease; another request may have changed
        # employee state while this request was waiting.
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        committed_face_id = employee.get(marker) if employee else None
        if committed_face_id:
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "enrolled",
                    "Employee photo enrolled successfully.",
                    employee_id=employee_id, name=employee.get("name", ""))
            return
        if not employee or not employee.get("active", False):
            _delete_request_faces(rekognition, image, request_external_id)
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "unknown_employee",
                    "The employee does not exist or is inactive.")
            return
        if int(employee.get("photo_count", 0)) >= int(settings["max_photos_per_employee"]):
            _delete_request_faces(rekognition, image, request_external_id)
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "limit_reached",
                    "The maximum number of enrollment photos has been reached.")
            return
        faces = rekognition.detect_faces(Image=image, Attributes=["DEFAULT"]).get("FaceDetails", [])
        if not faces:
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "no_face", "No face was detected.")
            return
        if len(faces) != 1:
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "multiple_faces",
                    "Only one person should be in the frame.")
            return
        quality = faces[0].get("Quality") or {}
        if (float(quality.get("Brightness", 0)) < float(settings["min_brightness"])
                or float(quality.get("Sharpness", 0)) < float(settings["min_sharpness"])):
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "low_quality",
                    "Image quality is too low. Please improve lighting and focus.")
            return

        matches = rekognition.search_faces_by_image(
            CollectionId=_required_env("COLLECTION_ID"),
            Image=image,
            FaceMatchThreshold=float(settings["face_match_threshold"]),
            MaxFaces=5,
            QualityFilter="AUTO",
        ).get("FaceMatches", [])
        if any(
            _external_employee_id((match.get("Face") or {}).get("ExternalImageId") or "")
            not in ("", employee_id)
            for match in matches
        ):
            _release_employee_lock(employees, employee_id, request_id)
            _finish(s3, bucket, key, results, request_id, "duplicate_face",
                    "This face is already enrolled to another employee.")
            return

        known_face_ids = set(employee.get("face_ids") or [])
        # A request-specific ExternalImageId makes an IndexFaces operation
        # recoverable even if the invocation stops before employee persistence.
        recovered = [
            (match.get("Face") or {}).get("FaceId")
            for match in matches
            if (match.get("Face") or {}).get("ExternalImageId") == request_external_id
            and (match.get("Face") or {}).get("FaceId")
            and (match.get("Face") or {}).get("FaceId") not in known_face_ids
        ]
        if recovered:
            face_id = recovered[0]
        else:
            indexed = rekognition.index_faces(
                CollectionId=_required_env("COLLECTION_ID"),
                Image=image,
                ExternalImageId=request_external_id,
                MaxFaces=1,
                QualityFilter="AUTO",
            )
            indexed_face_ids = [
                item["Face"]["FaceId"] for item in indexed.get("FaceRecords", [])
                if item.get("Face", {}).get("FaceId")
            ]
            if not indexed_face_ids:
                _release_employee_lock(employees, employee_id, request_id)
                _finish(s3, bucket, key, results, request_id, "no_face",
                        "The face could not be indexed. Please try another photo.")
                return
            face_id = indexed_face_ids[0]

        now = now_ist().isoformat(timespec="seconds")
        try:
            employees.update_item(
                Key={"employee_id": employee_id},
                UpdateExpression=(
                    "SET photo_count=if_not_exists(photo_count,:zero)+:one, "
                    "face_ids=list_append(if_not_exists(face_ids,:empty),:new_faces), "
                    "#marker=:face_id, updated_at=:now "
                    "REMOVE enrollment_lock_request, enrollment_lock_until"
                ),
                ConditionExpression=(
                    "active=:active AND attribute_not_exists(#marker) AND "
                    "(attribute_not_exists(photo_count) OR photo_count < :max) AND "
                    "enrollment_lock_request=:request"
                ),
                ExpressionAttributeNames={"#marker": marker},
                ExpressionAttributeValues={
                    ":zero": 0, ":one": 1, ":empty": [], ":new_faces": [face_id],
                    ":face_id": face_id, ":now": now, ":active": True,
                    ":max": int(settings["max_photos_per_employee"]),
                    ":request": request_id,
                },
            )
            indexed_face_ids = []
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            latest = employees.get_item(
                Key={"employee_id": employee_id}, ConsistentRead=True
            ).get("Item")
            if latest and latest.get(marker):
                indexed_face_ids = []
            else:
                if face_id not in set((latest or {}).get("face_ids") or []):
                    _delete_face_ids(rekognition, [face_id])
                    indexed_face_ids = []
                _release_employee_lock(employees, employee_id, request_id)
                code = "limit_reached" if latest and latest.get("active", False) else "unknown_employee"
                message = ("The maximum number of enrollment photos has been reached."
                           if code == "limit_reached" else
                           "The employee does not exist or is inactive.")
                _finish(s3, bucket, key, results, request_id, code, message)
                return

        _finish(s3, bucket, key, results, request_id, "enrolled",
                "Employee photo enrolled successfully.",
                employee_id=employee_id, name=employee.get("name", ""))
    except Exception:
        # Do not mark a retryable failure terminal and do not delete the image.
        # Keep the short lease; a later retry can reclaim it after expiry.
        LOGGER.exception("Enrollment processing failed; preserving image for retry")
        raise


def lambda_handler(event, context):
    for record in (event or {}).get("Records", []):
        try:
            _process_record(record)
        except Exception as exc:
            LOGGER.error("Enrollment processing failed (%s)", type(exc).__name__)
            raise
    return {"statusCode": 200, "body": "processed"}
