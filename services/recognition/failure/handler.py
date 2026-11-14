"""Finalize failed async recognition/enrollment events and remove retained images."""
import json
import logging
import os
from urllib.parse import unquote_plus
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
REGION = "ap-south-1"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _request_id_from_key(key: str) -> str | None:
    parts = key.split("/")
    if len(parts) == 2 and parts[0] == "captures" and parts[1].endswith(".jpg"):
        candidate = parts[1][:-4]
    elif len(parts) == 3 and parts[0] == "enroll" and parts[2].endswith(".jpg"):
        candidate = parts[2][:-4]
    else:
        return None
    try:
        parsed = UUID(candidate)
    except (ValueError, TypeError, AttributeError):
        return None
    return candidate if parsed.version == 4 else None


def _request_payload(body: str) -> dict:
    envelope = json.loads(body)
    payload = envelope.get("requestPayload")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("failure destination message has no requestPayload object")
    return payload


def _finalize_record(record: dict, bucket_name: str, results, s3) -> None:
    info = record.get("s3") or {}
    bucket = (info.get("bucket") or {}).get("name")
    encoded_key = (info.get("object") or {}).get("key")
    if bucket != bucket_name or not encoded_key:
        raise ValueError("failure event references an unexpected raw bucket or missing key")
    key = unquote_plus(encoded_key)
    request_id = _request_id_from_key(key)
    if not request_id:
        raise ValueError("failure event contains an invalid raw-image key")

    try:
        results.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #code=:error, #message=:message",
            ConditionExpression="#code=:pending",
            ExpressionAttributeNames={"#code": "code", "#message": "message"},
            ExpressionAttributeValues={
                ":error": "error",
                ":message": "Processing failed after automatic retries. Please retry the capture.",
                ":pending": "pending",
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        # The result is already terminal or has expired. Image cleanup remains
        # safe and must still happen.
    s3.delete_object(Bucket=bucket_name, Key=key)


def lambda_handler(event, context):
    table = boto3.resource("dynamodb", region_name=REGION).Table(
        _required_env("TABLE_SCAN_RESULTS")
    )
    s3 = boto3.client("s3", region_name=REGION)
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
                _finalize_record(record, bucket_name, table, s3)
        except Exception as exc:
            LOGGER.error("Failure-event recovery failed (%s)", type(exc).__name__)
            if message_id:
                failures.append({"itemIdentifier": message_id})
            else:
                raise

    return {"batchItemFailures": failures}
