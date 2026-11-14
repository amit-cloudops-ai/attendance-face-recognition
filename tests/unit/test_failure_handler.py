import json
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from services.recognition.failure import handler as failure


@pytest.fixture
def aws_env(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "ap-south-1")
        monkeypatch.setenv("TABLE_SCAN_RESULTS", "scan-results")
        monkeypatch.setenv("BUCKET_RAW", "attendance-raw")
        db = boto3.resource("dynamodb", region_name="ap-south-1")
        table = db.create_table(
            TableName="scan-results",
            KeySchema=[{"AttributeName": "request_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "request_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="attendance-raw",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        yield table, s3


def destination_event(request_id, key):
    original = {
        "Records": [{
            "s3": {
                "bucket": {"name": "attendance-raw"},
                "object": {"key": key.replace("/", "%2F")},
            }
        }]
    }
    return {
        "Records": [{
            "messageId": "message-1",
            "body": json.dumps({"version": "1.0", "requestPayload": original}),
        }]
    }


@pytest.mark.parametrize(
    "key,kind",
    [
        ("captures/{request_id}.jpg", "scan"),
        ("enroll/EMP001/{request_id}.jpg", "enroll"),
    ],
)
def test_failure_destination_marks_pending_result_error_and_deletes_image(aws_env, key, kind):
    table, s3 = aws_env
    request_id = str(uuid.uuid4())
    object_key = key.format(request_id=request_id)
    table.put_item(Item={
        "request_id": request_id, "kind": kind, "code": "pending",
        "message": "Processing", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")

    result = failure.lambda_handler(destination_event(request_id, object_key), None)
    item = table.get_item(Key={"request_id": request_id})["Item"]
    assert result == {"batchItemFailures": []}
    assert item["code"] == "error"
    assert "automatic retries" in item["message"]
    with pytest.raises(ClientError):
        s3.head_object(Bucket="attendance-raw", Key=object_key)


def test_failure_destination_preserves_existing_terminal_result(aws_env):
    table, s3 = aws_env
    request_id = str(uuid.uuid4())
    object_key = f"captures/{request_id}.jpg"
    table.put_item(Item={
        "request_id": request_id, "kind": "scan", "code": "matched",
        "message": "Already completed", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")

    failure.lambda_handler(destination_event(request_id, object_key), None)
    item = table.get_item(Key={"request_id": request_id})["Item"]
    assert item["code"] == "matched"
    assert item["message"] == "Already completed"
    with pytest.raises(ClientError):
        s3.head_object(Bucket="attendance-raw", Key=object_key)


def test_malformed_failure_message_is_returned_for_sqs_retry(aws_env):
    result = failure.lambda_handler({
        "Records": [{"messageId": "bad-message", "body": "{not-json"}]
    }, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad-message"}]}
