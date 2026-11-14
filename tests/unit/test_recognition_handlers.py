import json
import time
import uuid

import boto3
import pytest
from attendance_common import config
from attendance_common.auth import get_username, require_group
from moto import mock_aws
from services.recognition.presign import handler as presign
from services.recognition.recognize import handler as recognize
from services.recognition.result import handler as result


def api_event(group="kiosk", request_id=None):
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "cognito:groups": f"[{group}]", "cognito:username": "test-user"
        }}}},
        "pathParameters": {"request_id": request_id} if request_id else {},
    }


@pytest.fixture
def aws_env(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "ap-south-1")
        monkeypatch.setenv("TABLE_SCAN_RESULTS", "scan-results")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
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
        boto3.client("s3", region_name="ap-south-1").create_bucket(
            Bucket="attendance-raw",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        config._reset_cache()
        yield scans, employees
        config._reset_cache()


def body(response):
    return json.loads(response["body"])


def test_cognito_group_matching_uses_word_boundaries():
    event = api_event("admin")
    assert require_group(event, "admin") is None
    assert require_group(event, "kiosk")["statusCode"] == 403
    event["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = "[superadmin]"
    assert require_group(event, "admin")["statusCode"] == 403
    assert get_username(api_event()) == "test-user"


def test_presign_requires_kiosk_or_admin(aws_env):
    denied = presign.lambda_handler({"requestContext": {}}, None)
    assert denied["statusCode"] == 403


def test_presign_writes_pending_row_and_returns_constrained_post(aws_env):
    scans, _ = aws_env
    response = presign.lambda_handler(api_event(), None)
    assert response["statusCode"] == 200
    payload = body(response)
    assert uuid.UUID(payload["request_id"]).version == 4
    assert payload["expires_in"] == 60
    assert payload["upload"]["url"].startswith("https://")
    assert payload["upload"]["fields"]["key"] == f"captures/{payload['request_id']}.jpg"
    item = scans.get_item(Key={"request_id": payload["request_id"]})["Item"]
    assert item["kind"] == "scan" and item["code"] == "pending"
    assert item["ttl"] > int(time.time())


def test_result_requires_valid_group_and_uuid(aws_env):
    assert result.lambda_handler({"requestContext": {}}, None)["statusCode"] == 403
    invalid = result.lambda_handler(api_event(request_id="not-a-uuid"), None)
    assert invalid["statusCode"] == 400


def test_result_returns_only_contract_fields_and_not_found(aws_env):
    scans, _ = aws_env
    request_id = str(uuid.uuid4())
    assert result.lambda_handler(api_event(request_id=request_id), None)["statusCode"] == 404
    scans.put_item(Item={"request_id": request_id, "kind": "scan", "code": "matched",
        "message": "Welcome.", "created_at": "2026-11-14T09:00:00+05:30", "ttl": 9999999999,
        "employee_id": "EMP001", "name": "Priya", "time": "2026-11-14T09:00:00+05:30",
        "status": "present", "action": "clock_in"})
    payload = body(result.lambda_handler(api_event(request_id=request_id), None))
    assert payload == {"request_id": request_id, "kind": "scan", "code": "matched",
        "message": "Welcome.", "name": "Priya", "time": "2026-11-14T09:00:00+05:30",
        "status": "present", "action": "clock_in"}
    assert "ttl" not in payload and "employee_id" not in payload


class FakeS3:
    def __init__(self):
        self.deleted = []

    def head_object(self, **kwargs):
        return {}

    def delete_object(self, **kwargs):
        self.deleted.append(kwargs["Key"])


class FakeRekognition:
    def __init__(self, faces=None, matches=None):
        self.faces = faces if faces is not None else [{"Quality": {"Brightness": 90, "Sharpness": 90}}]
        self.matches = matches if matches is not None else [{"Similarity": 98.7, "Face": {"ExternalImageId": "EMP001"}}]
        self.detect_calls = 0
        self.search_calls = 0

    def detect_faces(self, **kwargs):
        self.detect_calls += 1
        return {"FaceDetails": self.faces}

    def search_faces_by_image(self, **kwargs):
        self.search_calls += 1
        return {"FaceMatches": self.matches}


def s3_event(request_id):
    return {"Records": [{"s3": {"bucket": {"name": "attendance-raw"},
        "object": {"key": f"captures%2F{request_id}.jpg"}}}]}


def seed_pending(scans, request_id):
    scans.put_item(Item={"request_id": request_id, "kind": "scan", "code": "pending",
        "message": "Pending", "created_at": "2026-11-14T09:00:00+05:30", "ttl": 9999999999})


def setup_worker(monkeypatch, scans, employees, rekognition, s3, record=None):
    monkeypatch.setattr(recognize.boto3, "client", lambda service, **kwargs:
        s3 if service == "s3" else rekognition)
    monkeypatch.setattr(recognize, "_table", lambda name:
        scans if name == "TABLE_SCAN_RESULTS" else employees)
    monkeypatch.setattr(recognize, "get_settings", lambda: {
        "min_brightness": 40, "min_sharpness": 40, "face_match_threshold": 95})
    if record is not None:
        monkeypatch.setattr(recognize, "record_scan", record)
    from datetime import datetime
    monkeypatch.setattr(recognize, "now_ist", lambda:
        datetime.fromisoformat("2026-11-14T09:15:00+05:30"))


def test_recognize_matched_records_attendance_and_deletes_image(aws_env, monkeypatch):
    scans, employees = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True})
    fake_s3, fake_rekognition = FakeS3(), FakeRekognition()
    called = {}

    def record(employee_id, scanned_at, confidence):
        called.update(employee_id=employee_id, confidence=confidence)
        return {"action": "clock_in", "status": "present",
            "clock_in": "2026-11-14T09:15:00+05:30", "clock_out": None}

    setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3, record)
    recognize.lambda_handler(s3_event(request_id), None)
    item = scans.get_item(Key={"request_id": request_id})["Item"]
    assert item["code"] == "matched" and item["action"] == "clock_in"
    assert called == {"employee_id": "EMP001", "confidence": 98.7}
    assert fake_s3.deleted == [f"captures/{request_id}.jpg"]


@pytest.mark.parametrize("faces,expected", [
    ([], "no_face"),
    ([{}, {}], "multiple_faces"),
    ([{"Quality": {"Brightness": 10, "Sharpness": 90}}], "low_quality"),
])
def test_recognize_face_quality_outcomes(aws_env, monkeypatch, faces, expected):
    scans, employees = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    fake_s3, fake_rekognition = FakeS3(), FakeRekognition(faces=faces)
    setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)
    recognize.lambda_handler(s3_event(request_id), None)
    assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == expected
    assert fake_s3.deleted == [f"captures/{request_id}.jpg"]


def test_recognize_no_match_inactive_and_missing_employee(aws_env, monkeypatch):
    scans, employees = aws_env
    for employee_id, active, matches, expected in [
        (None, None, [], "no_match"),
        ("EMP999", True, [{"Similarity": 99, "Face": {"ExternalImageId": "EMP999"}}], "no_match"),
        ("EMP001", False, [{"Similarity": 99, "Face": {"ExternalImageId": "EMP001"}}], "inactive"),
    ]:
        request_id = str(uuid.uuid4())
        seed_pending(scans, request_id)
        if employee_id and employee_id != "EMP999":
            employees.put_item(Item={"employee_id": employee_id, "name": "Test", "active": active})
        fake_s3, fake_rekognition = FakeS3(), FakeRekognition(matches=matches)
        setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)
        recognize.lambda_handler(s3_event(request_id), None)
        assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == expected
        assert fake_s3.deleted == [f"captures/{request_id}.jpg"]


def test_duplicate_event_is_noop_and_warmup_avoids_clients(aws_env, monkeypatch):
    scans, employees = aws_env
    request_id = str(uuid.uuid4())
    scans.put_item(Item={"request_id": request_id, "kind": "scan", "code": "matched",
        "message": "Done", "created_at": "now", "ttl": 9999999999})
    fake_s3, fake_rekognition = FakeS3(), FakeRekognition()
    setup_worker(monkeypatch, scans, employees, fake_rekognition, fake_s3)
    recognize.lambda_handler(s3_event(request_id), None)
    assert fake_rekognition.detect_calls == 0
    assert fake_s3.deleted == [f"captures/{request_id}.jpg"]
    assert recognize.lambda_handler({"warmup": True}, None) == {"statusCode": 200, "body": "warm"}


def test_recognize_exception_marks_error_and_still_deletes(aws_env, monkeypatch):
    scans, employees = aws_env
    request_id = str(uuid.uuid4())
    seed_pending(scans, request_id)
    fake_s3 = FakeS3()

    class BrokenRekognition:
        def detect_faces(self, **kwargs):
            raise RuntimeError("rekognition unavailable")

    setup_worker(monkeypatch, scans, employees, BrokenRekognition(), fake_s3)
    with pytest.raises(RuntimeError):
        recognize.lambda_handler(s3_event(request_id), None)
    assert scans.get_item(Key={"request_id": request_id})["Item"]["code"] == "error"
    assert fake_s3.deleted == [f"captures/{request_id}.jpg"]
