import json
import time
import uuid

import boto3
import pytest
from attendance_common import config
from moto import mock_aws

from services.recognition.enroll import handler as enroll
from services.recognition.enroll_url import handler as enroll_url
from services.recognition.faces_delete import handler as faces_delete


def event(group="admin", employee_id="EMP001"):
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "cognito:groups": f"[{group}]", "cognito:username": "admin-user"
        }}}},
        "pathParameters": {"employee_id": employee_id},
    }


@pytest.fixture
def aws_env(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "ap-south-1")
        monkeypatch.setenv("TABLE_SCAN_RESULTS", "scan-results")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_AUDIT", "audit")
        monkeypatch.setenv("BUCKET_RAW", "attendance-raw")
        monkeypatch.setenv("COLLECTION_ID", "attendance-dev-faces")
        db = boto3.resource("dynamodb", region_name="ap-south-1")
        scans = db.create_table(TableName="scan-results",
            KeySchema=[{"AttributeName": "request_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "request_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        employees = db.create_table(TableName="employees",
            KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        audit = db.create_table(TableName="audit",
            KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "audit_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST")
        boto3.client("s3", region_name="ap-south-1").create_bucket(
            Bucket="attendance-raw",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        config._reset_cache()
        yield scans, employees, audit
        config._reset_cache()


def response_body(response):
    return json.loads(response["body"])


def test_enroll_url_authorizes_admin_and_checks_employee(aws_env):
    _, employees, _ = aws_env
    assert enroll_url.lambda_handler(event("kiosk"), None)["statusCode"] == 403
    assert enroll_url.lambda_handler(event(employee_id="bad"), None)["statusCode"] == 400
    assert enroll_url.lambda_handler(event(), None)["statusCode"] == 404
    employees.put_item(Item={"employee_id": "EMP001", "active": False})
    assert enroll_url.lambda_handler(event(), None)["statusCode"] == 409


def test_enroll_url_creates_pending_result_and_limited_post(aws_env):
    scans, employees, _ = aws_env
    employees.put_item(Item={"employee_id": "EMP001", "active": True})
    result = enroll_url.lambda_handler(event(), None)
    assert result["statusCode"] == 200
    payload = response_body(result)
    request_id = payload["request_id"]
    assert uuid.UUID(request_id).version == 4
    assert payload["expires_in"] == 60
    assert payload["upload"]["fields"]["key"] == f"enroll/EMP001/{request_id}.jpg"
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert item["kind"] == "enroll" and item["code"] == "pending"
    assert item["ttl"] > int(time.time())


class FakeS3:
    def __init__(self):
        self.deleted = []

    def head_object(self, **kwargs):
        return {}

    def delete_object(self, **kwargs):
        self.deleted.append(kwargs["Key"])


class FakeRekognition:
    def __init__(self, faces=None, matches=None, face_id="face-001"):
        self.faces = faces if faces is not None else [
            {"Quality": {"Brightness": 90, "Sharpness": 90}}
        ]
        self.matches = matches if matches is not None else []
        self.face_id = face_id
        self.deleted = []
        self.index_calls = 0

    def detect_faces(self, **kwargs):
        return {"FaceDetails": self.faces}

    def search_faces_by_image(self, **kwargs):
        return {"FaceMatches": self.matches}

    def index_faces(self, **kwargs):
        self.index_calls += 1
        return {"FaceRecords": [{"Face": {"FaceId": self.face_id}}]}

    def delete_faces(self, **kwargs):
        self.deleted.extend(kwargs["FaceIds"])
        return {"DeletedFaces": kwargs["FaceIds"]}


def s3_event(employee_id, request_id):
    return {"Records": [{"s3": {"bucket": {"name": "attendance-raw"},
        "object": {"key": f"enroll%2F{employee_id}%2F{request_id}.jpg"}}}]}


def seed_pending(scans, request_id):
    scans.put_item(Item={"request_id": request_id, "kind": "enroll", "code": "pending",
        "message": "Pending", "created_at": "2026-11-14T09:00:00+05:30", "ttl": 9999999999})


def setup_worker(monkeypatch, scans, employees, rekognition, s3):
    monkeypatch.setattr(enroll.boto3, "client", lambda service, **kwargs:
        s3 if service == "s3" else rekognition)
    monkeypatch.setattr(enroll, "_table", lambda name:
        scans if name == "TABLE_SCAN_RESULTS" else employees)
    monkeypatch.setattr(enroll, "get_settings", lambda: {
        "min_brightness": 40, "min_sharpness": 40,
        "face_match_threshold": 95, "max_photos_per_employee": 5})
    from datetime import datetime
    monkeypatch.setattr(enroll, "now_ist", lambda:
        datetime.fromisoformat("2026-11-14T09:15:00+05:30"))


def test_enroll_indexes_face_updates_employee_and_deletes_raw_image(aws_env, monkeypatch):
    scans, employees, _ = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True,
        "photo_count": 0, "face_ids": []})
    fake_s3, fake_rekognition = FakeS3(), FakeRekognition()
    setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)
    enroll.lambda_handler(s3_event("EMP001", request_id), None)
    employee = employees.get_item(Key={"employee_id": "EMP001"})["Item"]
    result = scans.get_item(Key={"request_id": request_id})["Item"]
    assert employee["photo_count"] == 1 and employee["face_ids"] == ["face-001"]
    assert result["code"] == "enrolled" and result["employee_id"] == "EMP001"
    assert fake_s3.deleted == [f"enroll/EMP001/{request_id}.jpg"]


@pytest.mark.parametrize("faces,expected", [
    ([], "no_face"),
    ([{}, {}], "multiple_faces"),
    ([{"Quality": {"Brightness": 10, "Sharpness": 90}}], "low_quality"),
])
def test_enroll_rejects_face_count_and_quality(aws_env, monkeypatch, faces, expected):
    scans, employees, _ = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    employees.put_item(Item={"employee_id": "EMP001", "active": True, "photo_count": 0})
    fake_s3, fake_rekognition = FakeS3(), FakeRekognition(faces=faces)
    setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)
    enroll.lambda_handler(s3_event("EMP001", request_id), None)
    assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == expected
    assert fake_s3.deleted == [f"enroll/EMP001/{request_id}.jpg"]


def test_enroll_rejects_unknown_employee_limit_and_duplicate_face(aws_env, monkeypatch):
    scans, employees, _ = aws_env
    cases = [
        (None, "unknown_employee", []),
        ({"employee_id": "EMP001", "active": True, "photo_count": 5}, "limit_reached", []),
        ({"employee_id": "EMP001", "active": True, "photo_count": 0}, "duplicate_face",
         [{"Face": {"ExternalImageId": "EMP002"}, "Similarity": 99}]),
    ]
    for employee, expected, matches in cases:
        request_id = str(uuid.uuid4())
        seed_pending(scans, request_id)
        if employee:
            employees.put_item(Item=employee)
        fake_s3, fake_rekognition = FakeS3(), FakeRekognition(matches=matches)
        setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)
        enroll.lambda_handler(s3_event("EMP001", request_id), None)
        assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == expected
        assert fake_s3.deleted == [f"enroll/EMP001/{request_id}.jpg"]


def test_enroll_retryable_exception_preserves_pending_result_and_image(aws_env, monkeypatch):
    scans, employees, _ = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    employees.put_item(Item={"employee_id": "EMP001", "active": True, "photo_count": 0})
    fake_s3 = FakeS3()

    class BrokenRekognition:
        def detect_faces(self, **kwargs):
            raise RuntimeError("rekognition unavailable")

    setup_worker(monkeypatch, scans, employees, BrokenRekognition(), fake_s3)
    with pytest.raises(RuntimeError):
        enroll.lambda_handler(s3_event("EMP001", request_id), None)
    assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == "pending"
    assert fake_s3.deleted == []


def test_faces_delete_removes_templates_clears_employee_and_audits(aws_env, monkeypatch):
    _, employees, audit = aws_env
    employees.put_item(Item={"employee_id": "EMP001", "active": False,
        "photo_count": 2, "face_ids": ["face-a", "face-b"]})
    fake = FakeRekognition()
    monkeypatch.setattr(faces_delete.boto3, "client", lambda service, **kwargs: fake)
    response = faces_delete.lambda_handler(event(), None)
    assert response_body(response) == {"deleted": 2}
    employee = employees.get_item(Key={"employee_id": "EMP001"})["Item"]
    assert employee["photo_count"] == 0 and employee["face_ids"] == []
    audit_item = audit.scan()["Items"][0]
    assert audit_item["action"] == "faces_delete"
    assert audit_item["actor"] == "admin-user"
    assert audit_item["old"]["photo_count"] == 2
    assert fake.deleted == ["face-a", "face-b"]


def test_faces_delete_requires_admin_and_existing_employee(aws_env):
    assert faces_delete.lambda_handler(event("kiosk"), None)["statusCode"] == 403
    assert faces_delete.lambda_handler(event(employee_id="EMP999"), None)["statusCode"] == 404

 

def test_enrollment_retry_after_employee_commit_does_not_index_twice(aws_env, monkeypatch):
    scans, employees, _ = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True,
        "photo_count": 0, "face_ids": []})
    fake_s3, fake_rekognition = FakeS3(), FakeRekognition()
    setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)

    original_finish = enroll._update_result
    calls = {"count": 0}

    def fail_once(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary DynamoDB failure")
        return original_finish(*args, **kwargs)

    monkeypatch.setattr(enroll, "_update_result", fail_once)
    with pytest.raises(RuntimeError):
        enroll.lambda_handler(s3_event("EMP001", request_id), None)

    committed = employees.get_item(Key={"employee_id": "EMP001"})["Item"]
    assert committed["photo_count"] == 1
    assert committed["enrollment_" + request_id] == "face-001"
    assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == "pending"
    assert fake_s3.deleted == []

    monkeypatch.setattr(enroll, "_update_result", original_finish)
    enroll.lambda_handler(s3_event("EMP001", request_id), None)
    result = scans.get_item(Key={"request_id": request_id})["Item"]
    assert result["code"] == "enrolled"
    assert committed["photo_count"] == 1
    assert fake_rekognition.index_calls == 1
    assert fake_s3.deleted == [f"enroll/EMP001/{request_id}.jpg"]
