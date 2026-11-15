import json
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from services.recognition.failure import handler as failure


class FakeRekognition:
    def __init__(self, matches=None):
        self.matches = matches or []
        self.deleted = []

    def search_faces_by_image(self, **kwargs):
        return {"FaceMatches": self.matches}

    def delete_faces(self, **kwargs):
        self.deleted.extend(kwargs["FaceIds"])
        return {"DeletedFaces": kwargs["FaceIds"]}


@pytest.fixture
def aws_env(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("TABLE_SCAN_RESULTS", "scan-results")
        monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("BUCKET_RAW", "attendance-raw")
        monkeypatch.setenv("COLLECTION_ID", "attendance-dev-faces")
        db = boto3.resource("dynamodb", region_name="us-east-1")
        scans = db.create_table(
            TableName="scan-results",
            KeySchema=[{"AttributeName": "request_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "request_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        attendance = db.create_table(
            TableName="attendance",
            KeySchema=[
                {"AttributeName": "employee_id", "KeyType": "HASH"},
                {"AttributeName": "date", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "employee_id", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "date-index",
                "KeySchema": [
                    {"AttributeName": "date", "KeyType": "HASH"},
                    {"AttributeName": "employee_id", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        employees = db.create_table(
            TableName="employees",
            KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(
            Bucket="attendance-raw",
        )
        fake_rekognition = FakeRekognition()
        monkeypatch.setattr(
            failure.boto3, "client",
            lambda service, **kwargs: s3 if service == "s3" else fake_rekognition,
        )
        yield scans, attendance, employees, s3, fake_rekognition


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
def test_exhausted_failure_marks_uncommitted_request_error_and_deletes_image(
    aws_env, key, kind
):
    scans, _, _, s3, _ = aws_env
    request_id = str(uuid.uuid4())
    object_key = key.format(request_id=request_id)
    scans.put_item(Item={
        "request_id": request_id, "kind": kind, "code": "pending",
        "message": "Processing", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")

    result = failure.lambda_handler(destination_event(request_id, object_key), None)
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert result == {"batchItemFailures": []}
    assert item["code"] == "error"
    assert "automatic retries" in item["message"]
    with pytest.raises(ClientError):
        s3.head_object(Bucket="attendance-raw", Key=object_key)


def test_failure_recovers_scan_whose_attendance_write_committed(aws_env):
    scans, attendance, employees, s3, _ = aws_env
    request_id = str(uuid.uuid4())
    object_key = f"captures/{request_id}.jpg"
    outcome = {
        "action": "clock_in",
        "status": "present",
        "date": "2026-11-14",
        "clock_in": "2026-11-14T09:00:00+05:30",
        "clock_out": None,
    }
    scans.put_item(Item={
        "request_id": request_id, "kind": "scan", "code": "pending",
        "message": "Processing", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True})
    attendance.put_item(Item={
        "employee_id": "EMP001", "date": "2026-11-14",
        "clock_in": outcome["clock_in"], "status": "present",
        "scan_events": {request_id: outcome},
    })
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")

    failure.lambda_handler(destination_event(request_id, object_key), None)
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert item["code"] == "matched"
    assert item["employee_id"] == "EMP001"
    assert item["name"] == "Priya"
    assert item["action"] == "clock_in"
    assert item["time"] == outcome["clock_in"]
    with pytest.raises(ClientError):
        s3.head_object(Bucket="attendance-raw", Key=object_key)


def test_failure_recovers_enrollment_whose_employee_write_committed(aws_env):
    scans, _, employees, s3, rekognition = aws_env
    request_id = str(uuid.uuid4())
    object_key = f"enroll/EMP001/{request_id}.jpg"
    scans.put_item(Item={
        "request_id": request_id, "kind": "enroll", "code": "pending",
        "message": "Processing", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    employees.put_item(Item={
        "employee_id": "EMP001", "name": "Priya", "active": True,
        "photo_count": 1, "face_ids": ["face-001"],
        "enrollment_" + request_id: "face-001",
    })
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")

    failure.lambda_handler(destination_event(request_id, object_key), None)
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert item["code"] == "enrolled"
    assert item["employee_id"] == "EMP001"
    assert item["name"] == "Priya"
    assert rekognition.deleted == []
    with pytest.raises(ClientError):
        s3.head_object(Bucket="attendance-raw", Key=object_key)


def test_failure_rolls_back_uncommitted_request_scoped_face(aws_env):
    scans, _, employees, s3, rekognition = aws_env
    request_id = str(uuid.uuid4())
    object_key = f"enroll/EMP001/{request_id}.jpg"
    scans.put_item(Item={
        "request_id": request_id, "kind": "enroll", "code": "pending",
        "message": "Processing", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True})
    rekognition.matches = [{
        "Similarity": 99.9,
        "Face": {
            "ExternalImageId": "EMP001#" + request_id,
            "FaceId": "orphan-face",
        },
    }]
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")

    failure.lambda_handler(destination_event(request_id, object_key), None)
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert item["code"] == "error"
    assert rekognition.deleted == ["orphan-face"]
    with pytest.raises(ClientError):
        s3.head_object(Bucket="attendance-raw", Key=object_key)


def test_failure_destination_preserves_existing_terminal_result(aws_env):
    table, _, _, s3, _ = aws_env
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



def test_failure_scan_uses_strong_base_table_fallback_when_gsi_lags(aws_env, monkeypatch):
    scans, attendance, employees, s3, _ = aws_env
    request_id = str(uuid.uuid4())
    object_key = f"captures/{request_id}.jpg"
    outcome = {
        "action": "clock_in", "status": "present", "date": "2026-11-14",
        "clock_in": "2026-11-14T09:00:00+05:30", "clock_out": None,
    }
    scans.put_item(Item={
        "request_id": request_id, "kind": "scan", "code": "pending",
        "message": "Processing", "created_at": "2026-11-14T09:00:00+05:30",
        "ttl": 9999999999,
    })
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True})
    attendance.put_item(Item={
        "employee_id": "EMP001", "date": "2026-11-14", "clock_in": outcome["clock_in"],
        "status": "present", "scan_events": {request_id: outcome},
    })
    s3.put_object(Bucket="attendance-raw", Key=object_key, Body=b"image")
    monkeypatch.setattr(attendance, "query", lambda **kwargs: {"Items": []})

    failure.lambda_handler(destination_event(request_id, object_key), None)
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert item["code"] == "matched"
    assert item["employee_id"] == "EMP001"
