"""S3-triggered face recognition worker with idempotent results and image deletion."""
import logging
import os
from urllib.parse import unquote_plus
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from attendance_common.config import get_settings
from attendance_common.record_scan import record_scan
from attendance_common.tz import now_ist

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
REGION = "ap-south-1"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _table(env_name: str):
    return boto3.resource(
        "dynamodb", region_name=os.getenv("AWS_REGION", REGION)
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

    s3 = boto3.client("s3", region_name=REGION)
    results = None
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

        settings = get_settings()
        rekognition = boto3.client("rekognition", region_name=REGION)
        image = {"S3Object": {"Bucket": bucket, "Name": key}}
        detection = rekognition.detect_faces(Image=image, Attributes=["DEFAULT"])
        faces = detection.get("FaceDetails", [])
        if len(faces) == 0:
            _update_result(results, request_id, "no_face", "No face was detected.")
            return
        if len(faces) != 1:
            _update_result(results, request_id, "multiple_faces", "Only one person should be in the frame.")
            return
        quality = faces[0].get("Quality") or {}
        if (float(quality.get("Brightness", 0)) < float(settings["min_brightness"])
                or float(quality.get("Sharpness", 0)) < float(settings["min_sharpness"])):
            _update_result(results, request_id, "low_quality", "Image quality is too low. Please improve lighting and focus.")
            return

        matches = rekognition.search_faces_by_image(
            CollectionId=_required_env("COLLECTION_ID"),
            Image=image,
            FaceMatchThreshold=float(settings["face_match_threshold"]),
            MaxFaces=1,
            QualityFilter="AUTO",
        ).get("FaceMatches", [])
        if not matches:
            _update_result(results, request_id, "no_match", "Face not recognised. Please try again.")
            return
        face = (matches[0].get("Face") or {})
        employee_id = face.get("ExternalImageId")
        if not employee_id:
            _update_result(results, request_id, "no_match", "Face not recognised. Please try again.")
            return

        employees = _table("TABLE_EMPLOYEES")
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item")
        if not employee:
            _update_result(results, request_id, "no_match", "Face not recognised. Please try again.")
            return
        if not employee.get("active", False):
            _update_result(results, request_id, "inactive", "This employee account is inactive.")
            return

        similarity = float(matches[0].get("Similarity", 0))
        scan = record_scan(employee_id, now_ist(), similarity)
        action_time = scan.get("clock_out") if scan["action"] == "clock_out" else scan["clock_in"]
        _update_result(
            results, request_id, "matched", _message_for_scan(employee.get("name", "employee"), scan),
            employee_id=employee_id,
            name=employee.get("name", ""),
            time=action_time,
            status=scan["status"],
            action=scan["action"],
        )
    except Exception as exc:
        if results is not None:
            try:
                _update_result(results, request_id, "error", "Recognition failed. Please try again.")
            except Exception:
                LOGGER.exception("Unable to mark scan result as failed")
        LOGGER.error("Recognition processing failed (%s)", type(exc).__name__)
        raise
    finally:
        # DeleteObject is idempotent; a retry after an earlier deletion is harmless.
        s3.delete_object(Bucket=bucket, Key=key)


def lambda_handler(event, context):
    if event == {"warmup": True}:
        return {"statusCode": 200, "body": "warm"}
    for record in (event or {}).get("Records", []):
        _process_record(record)
    return {"statusCode": 200, "body": "processed"}
