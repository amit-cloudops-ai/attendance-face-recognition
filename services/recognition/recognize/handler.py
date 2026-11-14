"""S3-triggered face recognition worker with retry-safe result handling."""
import logging
import os
from datetime import datetime
from urllib.parse import unquote_plus
from uuid import UUID

import boto3
from attendance_common.config import get_settings
from attendance_common.record_scan import record_scan
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


def _table(env_name: str):
    return boto3.resource(
        "dynamodb", region_name=_region()
    ).Table(_required_env(env_name))


def _not_found(exc: ClientError) -> bool:
    error = exc.response.get("Error", {})
    metadata = exc.response.get("ResponseMetadata", {})
    return error.get("Code") in {"NoSuchKey", "NotFound", "404"} or metadata.get("HTTPStatusCode") == 404


def _update_result(table, request_id: str, code: str, message: str, **fields) -> bool:
    values = {":code": code, ":message": message, ":pending": "pending"}
    names = {"#code": "code", "#message": "message"}
    assignments = ["#code=:code", "#message=:message"]
    for index, (key, value) in enumerate(fields.items()):
        name, token = f"#field{index}", f":value{index}"
        names[name] = key
        values[token] = value
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


def _request_from_key(key: str) -> str | None:
    if not key.startswith("captures/") or not key.endswith(".jpg"):
        return None
    candidate = key[len("captures/"):-4]
    try:
        parsed = UUID(candidate)
    except (ValueError, AttributeError):
        return None
    return candidate if parsed.version == 4 else None


def _message_for_scan(employee_name: str, scan: dict) -> str:
    action = scan["action"]
    if action == "clock_in":
        return f"Welcome, {employee_name}. Clocked in at {scan['clock_in'][11:16]}."
    if action == "clock_out":
        return f"Clock-out recorded at {scan['clock_out'][11:16]}."
    return f"Already clocked in at {scan['clock_in'][11:16]}."


def _finish(s3, bucket: str, key: str, results, request_id: str, code: str,
            message: str, **fields) -> None:
    # The terminal result is durable before the biometric image is removed.
    # If either operation fails, Lambda retries; a terminal retry only repeats
    # the idempotent DeleteObject operation.
    _update_result(results, request_id, code, message, **fields)
    s3.delete_object(Bucket=bucket, Key=key)


def _process_record(record: dict) -> None:
    s3_info = record.get("s3") or {}
    bucket = (s3_info.get("bucket") or {}).get("name")
    encoded_key = (s3_info.get("object") or {}).get("key")
    if not bucket or not encoded_key:
        return
    key = unquote_plus(encoded_key)
    request_id = _request_from_key(key)
    if not request_id:
        return

    s3 = boto3.client("s3", region_name=_region())
    results = _table("TABLE_SCAN_RESULTS")
    pending = results.get_item(
        Key={"request_id": request_id}, ConsistentRead=True
    ).get("Item")
    if not pending or pending.get("code") != "pending":
        # A duplicate S3 notification after a terminal result is cleanup-only.
        s3.delete_object(Bucket=bucket, Key=key)
        return

    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if _not_found(exc):
            _finish(s3, bucket, key, results, request_id, "error",
                    "The uploaded image is no longer available.")
            return
        raise

    settings = get_settings()
    rekognition = boto3.client("rekognition", region_name=_region())
    image = {"S3Object": {"Bucket": bucket, "Name": key}}
    detection = rekognition.detect_faces(Image=image, Attributes=["DEFAULT"])
    faces = detection.get("FaceDetails", [])
    if len(faces) == 0:
        _finish(s3, bucket, key, results, request_id, "no_face", "No face was detected.")
        return
    if len(faces) != 1:
        _finish(s3, bucket, key, results, request_id, "multiple_faces",
                "Only one person should be in the frame.")
        return
    quality = faces[0].get("Quality") or {}
    if (float(quality.get("Brightness", 0)) < float(settings["min_brightness"])
            or float(quality.get("Sharpness", 0)) < float(settings["min_sharpness"])):
        _finish(s3, bucket, key, results, request_id, "low_quality",
                "Image quality is too low. Please improve lighting and focus.")
        return

    matches = rekognition.search_faces_by_image(
        CollectionId=_required_env("COLLECTION_ID"),
        Image=image,
        FaceMatchThreshold=float(settings["face_match_threshold"]),
        MaxFaces=1,
        QualityFilter="AUTO",
    ).get("FaceMatches", [])
    if not matches:
        _finish(s3, bucket, key, results, request_id, "no_match",
                "Face not recognised. Please try again.")
        return
    face = matches[0].get("Face") or {}
    external_image_id = face.get("ExternalImageId") or ""
    # New enrollment IDs include the originating request. Older collection
    # entries used the employee ID directly and remain readable.
    employee_id = external_image_id.split("#", 1)[0]
    if not employee_id:
        _finish(s3, bucket, key, results, request_id, "no_match",
                "Face not recognised. Please try again.")
        return

    employees = _table("TABLE_EMPLOYEES")
    employee = employees.get_item(
        Key={"employee_id": employee_id}, ConsistentRead=True
    ).get("Item")
    if not employee:
        _finish(s3, bucket, key, results, request_id, "no_match",
                "Face not recognised. Please try again.")
        return
    if not employee.get("active", False):
        _finish(s3, bucket, key, results, request_id, "inactive",
                "This employee account is inactive.")
        return

    # created_at is written before the presigned URL is returned. Using it
    # makes delayed S3 notifications and retries retain the original scan time.
    captured_at = datetime.fromisoformat(pending["created_at"])
    scan = record_scan(employee_id, captured_at, float(matches[0].get("Similarity", 0)),
                       request_id=request_id)
    action_time = scan.get("clock_out") if scan["action"] == "clock_out" else scan["clock_in"]
    _finish(
        s3, bucket, key, results, request_id, "matched",
        _message_for_scan(employee.get("name", "employee"), scan),
        employee_id=employee_id,
        name=employee.get("name", ""),
        time=action_time,
        status=scan["status"],
        action=scan["action"],
    )


def lambda_handler(event, context):
    if event == {"warmup": True}:
        return {"statusCode": 200, "body": "warm"}
    for record in (event or {}).get("Records", []):
        try:
            _process_record(record)
        except Exception as exc:
            # Do not write a terminal error or delete the source image here.
            # Lambda's async retry policy must be allowed to retry this event.
            LOGGER.error("Recognition processing failed (%s)", type(exc).__name__)
            raise
    return {"statusCode": 200, "body": "processed"}
