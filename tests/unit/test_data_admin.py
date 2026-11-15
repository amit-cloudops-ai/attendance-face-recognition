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
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
        monkeypatch.setenv("TABLE_CONFIG", "config")
        monkeypatch.setenv("TABLE_AUDIT", "audit")
        db = boto3.resource("dynamodb", region_name="us-east-1")
        monkeypatch.setattr(boto3, "resource", lambda *args, **kwargs: db)
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



def test_override_audit_and_attendance_are_written_in_one_transaction(admin_resources, monkeypatch):
    _, attendance, _, audit = admin_resources
    client = attendance.meta.client
    original = client.transact_write_items
    calls = []

    def capture(**kwargs):
        calls.append(kwargs["TransactItems"])
        return original(**kwargs)

    monkeypatch.setattr(client, "transact_write_items", capture)
    response = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13", "status": "present",
        "clock_in": "2026-11-13T09:00:00+05:30", "reason": "Verified.",
    }), None)
    assert response["statusCode"] == 200
    assert len(calls) == 1
    assert [next(iter(action)) for action in calls[0]] == ["Put", "Put"]
    assert len(audit.scan()["Items"]) == 1


def test_override_transaction_failure_writes_neither_record(admin_resources, monkeypatch):
    from botocore.exceptions import ClientError

    _, attendance, _, audit = admin_resources

    def fail(**kwargs):
        raise ClientError({"Error": {"Code": "InternalServerError", "Message": "simulated"}}, "TransactWriteItems")

    monkeypatch.setattr(attendance.meta.client, "transact_write_items", fail)
    response = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13", "status": "present",
        "clock_in": "2026-11-13T09:00:00+05:30", "reason": "Verified.",
    }), None)
    assert response["statusCode"] == 500
    assert attendance.scan()["Items"] == []
    assert audit.scan()["Items"] == []


def test_override_detects_concurrent_attendance_change(admin_resources, monkeypatch):
    _, attendance, _, audit = admin_resources
    client = attendance.meta.client
    original = client.transact_write_items

    def race(**kwargs):
        attendance.put_item(Item={
            "employee_id": "EMP001", "date": "2026-11-13",
            "status": "present", "clock_in": "2026-11-13T08:00:00+05:30",
            "updated_at": "2026-11-13T08:00:00+05:30",
        })
        return original(**kwargs)

    monkeypatch.setattr(client, "transact_write_items", race)
    response = override_handler.lambda_handler(admin_event({
        "employee_id": "EMP001", "date": "2026-11-13", "status": "late",
        "clock_in": "2026-11-13T09:00:00+05:30", "reason": "Verified.",
    }), None)
    assert response["statusCode"] == 409
    assert attendance.get_item(Key={"employee_id": "EMP001", "date": "2026-11-13"})["Item"]["clock_in"] == "2026-11-13T08:00:00+05:30"
    assert audit.scan()["Items"] == []


def test_settings_update_and_audit_are_transactional(admin_resources, monkeypatch):
    _, _, settings, audit = admin_resources
    client = settings.meta.client
    original = client.transact_write_items
    calls = []

    def capture(**kwargs):
        calls.append(kwargs["TransactItems"])
        return original(**kwargs)

    monkeypatch.setattr(client, "transact_write_items", capture)
    response = settings_handler.lambda_handler(admin_event({"grace_minutes": 12}, method="PUT"), None)
    assert response["statusCode"] == 200
    assert len(calls) == 1
    assert [next(iter(action)) for action in calls[0]] == ["Put", "Put"]
    assert len(audit.scan()["Items"]) == 1


def test_settings_transaction_failure_preserves_config_and_audit(admin_resources, monkeypatch):
    from botocore.exceptions import ClientError

    _, _, settings, audit = admin_resources

    def fail(**kwargs):
        raise ClientError({"Error": {"Code": "InternalServerError", "Message": "simulated"}}, "TransactWriteItems")

    monkeypatch.setattr(settings.meta.client, "transact_write_items", fail)
    response = settings_handler.lambda_handler(admin_event({"grace_minutes": 12}, method="PUT"), None)
    assert response["statusCode"] == 500
    assert settings.get_item(Key={"pk": "SETTINGS"}).get("Item") is None
    assert audit.scan()["Items"] == []


def test_settings_update_detects_stale_concurrent_write(admin_resources, monkeypatch):
    _, _, settings, audit = admin_resources
    settings.put_item(Item={"pk": "SETTINGS", "grace_minutes": 5, "updated_at": "old"})
    client = settings.meta.client
    original = client.transact_write_items

    def race(**kwargs):
        settings.put_item(Item={"pk": "SETTINGS", "grace_minutes": 8, "updated_at": "newer"})
        return original(**kwargs)

    monkeypatch.setattr(client, "transact_write_items", race)
    response = settings_handler.lambda_handler(admin_event({"debounce_minutes": 15}, method="PUT"), None)
    assert response["statusCode"] == 409
    assert settings.get_item(Key={"pk": "SETTINGS"})["Item"]["grace_minutes"] == 8
    assert audit.scan()["Items"] == []
