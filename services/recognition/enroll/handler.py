"""Index one consented employee photo and always remove its raw S3 object."""
import logging
import os
import re
from urllib.parse import unquote_plus
from uuid import UUID

import boto3
from attendance_common.config import get_settings
from attendance_common.tz import now_ist
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
_EMPLOYEE_ID = re.compile(r"^[A-Z0-9_-]{3,20}$")
REGION = "ap-south-1"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _table(env_name: str):
    return boto3.resource("dynamodb", region_name=REGION).Table(_required_env(env_name))


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
    s3 = boto3.client("s3", region_name=REGION)
    results = None
    rekognition = None
    indexed_face_ids = []
    try:
        results = _table("TABLE_SCAN_RESULTS")
        pending = results.get_item(
            Key={"request_id": request_id}, ConsistentRead=True
        ).get("Item")
        if not pending or pending.get("code") != "pending":
            return
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if _not_found(exc):
                return
            raise

        employees = _table("TABLE_EMPLOYEES")
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        if not employee or not employee.get("active", False):
            _update_result(results, request_id, "unknown_employee",
                           "The employee does not exist or is inactive.")
            return

        settings = get_settings()
        if int(employee.get("photo_count", 0)) >= int(settings["max_photos_per_employee"]):
            _update_result(results, request_id, "limit_reached",
                           "The maximum number of enrollment photos has been reached.")
            return

        rekognition = boto3.client("rekognition", region_name=REGION)
        image = {"S3Object": {"Bucket": bucket, "Name": key}}
        faces = rekognition.detect_faces(Image=image, Attributes=["DEFAULT"]).get("FaceDetails", [])
        if not faces:
            _update_result(results, request_id, "no_face", "No face was detected.")
            return
        if len(faces) != 1:
            _update_result(results, request_id, "multiple_faces",
                           "Only one person should be in the frame.")
            return
        quality = faces[0].get("Quality") or {}
        if (float(quality.get("Brightness", 0)) < float(settings["min_brightness"])
                or float(quality.get("Sharpness", 0)) < float(settings["min_sharpness"])):
            _update_result(results, request_id, "low_quality",
                           "Image quality is too low. Please improve lighting and focus.")
            return

        matches = rekognition.search_faces_by_image(
            CollectionId=_required_env("COLLECTION_ID"),
            Image=image,
            FaceMatchThreshold=float(settings["face_match_threshold"]),
            MaxFaces=1,
            QualityFilter="AUTO",
        ).get("FaceMatches", [])
        if any((match.get("Face") or {}).get("ExternalImageId") not in (None, employee_id)
               for match in matches):
            _update_result(results, request_id, "duplicate_face",
                           "This face is already enrolled to another employee.")
            return

        indexed = rekognition.index_faces(
            CollectionId=_required_env("COLLECTION_ID"),
            Image=image,
            ExternalImageId=employee_id,
            MaxFaces=1,
            QualityFilter="AUTO",
        )
        indexed_face_ids = [
            item["Face"]["FaceId"] for item in indexed.get("FaceRecords", [])
            if item.get("Face", {}).get("FaceId")
        ]
        if not indexed_face_ids:
            _update_result(results, request_id, "no_face",
                           "The face could not be indexed. Please try another photo.")
            return

        now = now_ist().isoformat(timespec="seconds")
        try:
            employees.update_item(
                Key={"employee_id": employee_id},
                UpdateExpression=(
                    "SET photo_count=if_not_exists(photo_count,:zero)+:one, "
                    "face_ids=list_append(if_not_exists(face_ids,:empty),:new_faces), "
                    "updated_at=:now"
                ),
                ConditionExpression=(
                    "active=:active AND (attribute_not_exists(photo_count) OR photo_count < :max)"
                ),
                ExpressionAttributeValues={
                    ":zero": 0, ":one": 1, ":empty": [], ":new_faces": indexed_face_ids,
                    ":now": now, ":active": True,
                    ":max": int(settings["max_photos_per_employee"]),
                },
            )
            indexed_face_ids = []
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            rekognition.delete_faces(
                CollectionId=_required_env("COLLECTION_ID"), FaceIds=indexed_face_ids
            )
            indexed_face_ids = []
            latest = employees.get_item(
                Key={"employee_id": employee_id}, ConsistentRead=True
            ).get("Item")
            code = "limit_reached" if latest and latest.get("active", False) else "unknown_employee"
            message = ("The maximum number of enrollment photos has been reached."
                       if code == "limit_reached" else
                       "The employee does not exist or is inactive.")
            _update_result(results, request_id, code, message)
            return

        _update_result(
            results, request_id, "enrolled", "Employee photo enrolled successfully.",
            employee_id=employee_id, name=employee.get("name", ""),
        )
    except Exception as exc:
        if indexed_face_ids and rekognition is not None:
            try:
                rekognition.delete_faces(
                    CollectionId=_required_env("COLLECTION_ID"), FaceIds=indexed_face_ids
                )
            except Exception:
                LOGGER.exception("Unable to roll back partially indexed enrollment faces")
        if results is not None:
            try:
                _update_result(results, request_id, "error", "Enrollment failed. Please try again.")
            except Exception:
                LOGGER.exception("Unable to mark enrollment result as failed")
        LOGGER.error("Enrollment processing failed (%s)", type(exc).__name__)
        raise
    finally:
        s3.delete_object(Bucket=bucket, Key=key)


def lambda_handler(event, context):
    for record in (event or {}).get("Records", []):
        _process_record(record)
    return {"statusCode": 200, "body": "processed"}
