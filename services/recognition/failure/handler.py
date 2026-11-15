"""Recover exhausted async recognition/enrollment invocations without losing commits."""
import json
import logging
import os
from datetime import datetime
from urllib.parse import unquote_plus
from uuid import UUID
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")
IST = ZoneInfo("Asia/Kolkata")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _parse_key(key: str) -> tuple[str, str | None, str] | None:
    parts = key.split("/")
    if len(parts) == 2 and parts[0] == "captures" and parts[1].endswith(".jpg"):
        kind, employee_id, candidate = "scan", None, parts[1][:-4]
    elif len(parts) == 3 and parts[0] == "enroll" and parts[2].endswith(".jpg"):
        kind, employee_id, candidate = "enroll", parts[1], parts[2][:-4]
    else:
        return None
    try:
        parsed = UUID(candidate)
    except (ValueError, TypeError, AttributeError):
        return None
    if parsed.version != 4:
        return None
    return kind, employee_id, candidate


def _request_payload(body: str) -> dict:
    envelope = json.loads(body)
    payload = envelope.get("requestPayload")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise TypeError("failure destination message has no requestPayload object")
    return payload


def _set_result(results, request_id: str, code: str, message: str, **fields) -> bool:
    names = {"#code": "code", "#message": "message"}
    values = {":code": code, ":message": message, ":pending": "pending"}
    assignments = ["#code=:code", "#message=:message"]
    for index, (key, value) in enumerate(fields.items()):
        name, token = f"#field{index}", f":value{index}"
        names[name], values[token] = key, value
        assignments.append(f"{name}={token}")
    try:
        results.update_item(
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


def _scan_outcome(attendance, request_id: str, captured_at: str) -> tuple[str, dict] | None:
    business_date = datetime.fromisoformat(captured_at).astimezone(IST).date().isoformat()
    response = attendance.query(
        IndexName="date-index",
        KeyConditionExpression=Key("date").eq(business_date),
    )
    while True:
        for item in response.get("Items", []):
            outcome = (item.get("scan_events") or {}).get(request_id)
            if outcome:
                return item["employee_id"], outcome
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        response = attendance.query(
            IndexName="date-index",
            KeyConditionExpression=Key("date").eq(business_date),
            ExclusiveStartKey=last_key,
        )

    # GSI reads are eventually consistent. The failure destination must not
    # turn a committed scan into an error merely because the index lags.
    # This expensive strong read is restricted to the rare exhausted-retry path.
    response = attendance.scan(ConsistentRead=True)
    while True:
        for item in response.get("Items", []):
            if item.get("date") != business_date:
                continue
            outcome = (item.get("scan_events") or {}).get(request_id)
            if outcome:
                return item["employee_id"], outcome
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return None
        response = attendance.scan(
            ConsistentRead=True, ExclusiveStartKey=last_key
        )


def _scan_message(name: str, outcome: dict) -> str:
    action = outcome["action"]
    if action == "clock_in":
        return f"Welcome, {name}. Clocked in at {outcome['clock_in'][11:16]}."
    if action == "clock_out":
        return f"Clock-out recorded at {outcome['clock_out'][11:16]}."
    return f"Already clocked in at {outcome['clock_in'][11:16]}."


def _recover_scan(results, attendance, employees, request_id: str, pending: dict) -> None:
    found = _scan_outcome(attendance, request_id, pending["created_at"])
    if found:
        employee_id, outcome = found
        employee = employees.get_item(
            Key={"employee_id": employee_id}, ConsistentRead=True
        ).get("Item") or {}
        name = employee.get("name", "employee")
        action_time = (
            outcome.get("clock_out")
            if outcome["action"] == "clock_out"
            else outcome["clock_in"]
        )
        _set_result(
            results, request_id, "matched", _scan_message(name, outcome),
            employee_id=employee_id,
            name=name,
            time=action_time,
            status=outcome["status"],
            action=outcome["action"],
        )
        return

    _set_result(
        results, request_id, "error",
        "Recognition failed after automatic retries. Please retry the capture.",
    )


def _recover_enrollment(results, employees, rekognition, bucket: str, key: str,
                        request_id: str, employee_id: str) -> None:
    employee = employees.get_item(
        Key={"employee_id": employee_id}, ConsistentRead=True
    ).get("Item") or {}
    marker = f"enrollment_{request_id}"
    if employee.get(marker):
        _set_result(
            results, request_id, "enrolled", "Employee photo enrolled successfully.",
            employee_id=employee_id, name=employee.get("name", ""),
        )
        return

    # IndexFaces may have succeeded just before the worker failed to persist
    # the FaceId. Remove only templates carrying this exact request identity.
    matches = rekognition.search_faces_by_image(
        CollectionId=_required_env("COLLECTION_ID"),
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        FaceMatchThreshold=0.0,
        MaxFaces=10,
        QualityFilter="NONE",
    ).get("FaceMatches", [])
    external_id = f"{employee_id}#{request_id}"
    orphan_ids = [
        (match.get("Face") or {}).get("FaceId")
        for match in matches
        if (match.get("Face") or {}).get("ExternalImageId") == external_id
        and (match.get("Face") or {}).get("FaceId")
    ]
    if orphan_ids:
        response = rekognition.delete_faces(
            CollectionId=_required_env("COLLECTION_ID"),
            FaceIds=orphan_ids,
        )
        confirmed = set(response.get("DeletedFaces", []))
        for failure in response.get("UnsuccessfulFaceDeletions", []):
            if failure.get("Reason") in {"FACE_NOT_FOUND", "RESOURCE_NOT_FOUND"}:
                confirmed.add(failure.get("FaceId"))
            else:
                raise RuntimeError("Rekognition could not remove an uncommitted enrollment face")
        if confirmed != set(orphan_ids):
            raise RuntimeError("Rekognition did not confirm cleanup of every uncommitted face")
    _set_result(
        results, request_id, "error",
        "Enrollment failed after automatic retries. Please retry the photo.",
    )


def _finalize_record(record: dict, bucket_name: str, results, attendance,
                     employees, s3, rekognition) -> None:
    info = record.get("s3") or {}
    bucket = (info.get("bucket") or {}).get("name")
    encoded_key = (info.get("object") or {}).get("key")
    if bucket != bucket_name or not encoded_key:
        raise ValueError("failure event references an unexpected raw bucket or missing key")
    key = unquote_plus(encoded_key)
    parsed = _parse_key(key)
    if not parsed:
        raise ValueError("failure event contains an invalid raw-image key")
    kind, employee_id, request_id = parsed

    pending = results.get_item(
        Key={"request_id": request_id}, ConsistentRead=True
    ).get("Item")
    if pending and pending.get("code") == "pending":
        if kind == "scan" and pending.get("kind") == "scan":
            _recover_scan(results, attendance, employees, request_id, pending)
        elif kind == "enroll" and pending.get("kind") == "enroll":
            _recover_enrollment(
                results, employees, rekognition, bucket_name, key,
                request_id, employee_id,
            )
        else:
            _set_result(
                results, request_id, "error",
                "The failed upload did not match its original request type.",
            )

    # The result is terminal (or expired) before the raw image is deleted.
    s3.delete_object(Bucket=bucket_name, Key=key)


def lambda_handler(event, context):
    db = boto3.resource("dynamodb", region_name=_region())
    results = db.Table(_required_env("TABLE_SCAN_RESULTS"))
    attendance = db.Table(_required_env("TABLE_ATTENDANCE"))
    employees = db.Table(_required_env("TABLE_EMPLOYEES"))
    s3 = boto3.client("s3", region_name=_region())
    rekognition = boto3.client("rekognition", region_name=_region())
    bucket_name = _required_env("BUCKET_RAW")
    failures = []

    for message in (event or {}).get("Records", []):
        message_id = message.get("messageId")
        try:
            payload = _request_payload(message.get("body", ""))
            records = payload.get("Records")
            if not isinstance(records, list) or not records:
                raise ValueError("failed invocation did not contain S3 records")
            for record in records:
                _finalize_record(
                    record, bucket_name, results, attendance, employees,
                    s3, rekognition,
                )
        except Exception as exc:
            LOGGER.error("Failure-event recovery failed (%s)", type(exc).__name__)
            if message_id:
                failures.append({"itemIdentifier": message_id})
            else:
                raise

    return {"batchItemFailures": failures}
