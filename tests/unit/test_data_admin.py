import json

import boto3
import pytest
from attendance_common import config
from moto import mock_aws

from services.data.override import handler as override_handler
from services.data.settings import handler as settings_handler


def admin_event(body=None, method="POST", group="admin"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {
                "cognito:groups": f"[{group}]",
                "cognito:username": "hr-admin",
                "sub": "admin-subject",
            }}},
            "http": {"method": method},
        },
        "body": json.dumps(body or {}),
    }


@pytest.fixture
def admin_resources(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "ap-south-1")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
        monkeypatch.setenv("TABLE_CONFIG", "config")
        monkeypatch.setenv("TABLE_AUDIT", "audit")
        db = boto3.resource("dynamodb", region_name="ap-south-1")
        employees = db.create_table(
            TableName="employees",
            KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
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
            BillingMode="PAY_PER_REQUEST",
        )
        settings = db.create_table(
            TableName="config",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        audit = db.create_table(
            TableName="audit",
            KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "audit_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        employees.put_item(Item={"employee_id": "EMP001", "name": "Priya", "active": True})
        config._reset_cache()
        yield employees, attendance, settings, audit
        config._reset_cache()


def payload(response):
    return json.loads(response["body"])


def test_override_writes_admin_record_and_audit(admin_resources):
    _, attendance, _, audit = admin_resources
    response = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001",
        "date": "2026-11-13",
        "status": "late",
        "clock_in": "2026-11-13T09:45:00+05:30",
        "clock_out": "2026-11-13T18:00:00+05:30",
        "reason": "Reception register confirmed the late arrival.",
    }), None)
    record = payload(response)
    assert response["statusCode"] == 200
    assert record["status"] == "late"
    assert record["source"] == "admin"
    assert record["updated_by"] == "hr-admin"
    stored = attendance.get_item(Key={"employee_id": "EMP001", "date": "2026-11-13"})["Item"]
    audit_item = audit.scan()["Items"][0]
    assert stored["clock_in"] == "2026-11-13T09:45:00+05:30"
    assert audit_item["action"] == "override"
    assert audit_item["reason"] == "Reception register confirmed the late arrival."


def test_override_requires_reason_and_valid_clock_in(admin_resources):
    missing_reason = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13",
        "clock_in": "2026-11-13T09:00:00+05:30",
    }), None)
    missing_clock = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13",
        "status": "present", "reason": "Verified against register.",
    }), None)
    assert missing_reason["statusCode"] == 400
    assert payload(missing_reason)["error"]["code"] == "reason_required"
    assert missing_clock["statusCode"] == 400
    assert payload(missing_clock)["error"]["code"] == "clock_in_required"


def test_override_rejects_naive_or_wrong_business_date_timestamp(admin_resources):
    naive = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13",
        "clock_in": "2026-11-13T09:00:00", "reason": "Verified.",
    }), None)
    wrong_day = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13",
        "clock_in": "2026-11-12T12:00:00+00:00", "reason": "Verified.",
    }), None)
    assert naive["statusCode"] == 400
    assert wrong_day["statusCode"] == 400


def test_override_absent_record_has_no_clock_times(admin_resources):
    _, attendance, _, audit = admin_resources
    response = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13",
        "status": "absent", "reason": "Approved leave was entered incorrectly.",
    }), None)
    assert response["statusCode"] == 200
    item = attendance.get_item(Key={"employee_id": "EMP001", "date": "2026-11-13"})["Item"]
    assert item["status"] == "absent"
    assert "clock_in" not in item and "clock_out" not in item
    assert audit.scan()["Items"][0]["action"] == "override"


def test_override_checks_employee_and_admin_group(admin_resources):
    missing = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP999", "date": "2026-11-13",
        "clock_in": "2026-11-13T09:00:00+05:30", "reason": "Verified.",
    }), None)
    denied = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13",
        "clock_in": "2026-11-13T09:00:00+05:30", "reason": "Verified.",
    }, group="kiosk"), None)
    assert missing["statusCode"] == 404
    assert denied["statusCode"] == 403


def test_settings_get_returns_defaults_and_put_persists_with_audit(admin_resources):
    _, _, settings, audit = admin_resources
    initial = settings_handler.lambda_handler(admin_event(method="GET"), None)
    assert initial["statusCode"] == 200
    assert payload(initial)["face_match_threshold"] == 95
    updated = settings_handler.lambda_handler(admin_event({
        "face_match_threshold": 97,
        "grace_minutes": 10,
        "weekend_days": [5, 6],
    }, method="PUT"), None)
    result = payload(updated)
    assert updated["statusCode"] == 200
    assert result["face_match_threshold"] == 97
    assert result["grace_minutes"] == 10
    assert result["weekend_days"] == [5, 6]
    stored = settings.get_item(Key={"pk": "SETTINGS"})["Item"]
    assert stored["face_match_threshold"] == 97
    audit_item = audit.scan()["Items"][0]
    assert audit_item["action"] == "settings_update"
    assert audit_item["actor"] == "hr-admin"


@pytest.mark.parametrize("body", [
    {"face_match_threshold": 101},
    {"grace_minutes": -1},
    {"debounce_minutes": 0},
    {"weekend_days": [6, 6]},
    {"weekend_days": [0, 7]},
    {"unknown_setting": 1},
    {},
])
def test_settings_rejects_invalid_or_empty_updates(admin_resources, body):
    response = settings_handler.lambda_handler(admin_event(body, method="PUT"), None)
    assert response["statusCode"] == 400


def test_settings_requires_admin_group(admin_resources):
    response = settings_handler.lambda_handler(admin_event(method="GET", group="kiosk"), None)
    assert response["statusCode"] == 403
