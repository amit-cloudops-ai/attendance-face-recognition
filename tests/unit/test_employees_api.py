import json
import sys
import types

import boto3
from moto import mock_aws

from services.data.employees.handler import handler


def install_auth(monkeypatch):
    auth = types.ModuleType("attendance_common.auth")
    auth.require_group = lambda event, group: True
    auth.get_username = lambda event: "test-admin"
    monkeypatch.setitem(sys.modules, "attendance_common.auth", auth)


def setup_tables(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
    monkeypatch.setenv("TABLE_AUDIT", "audit")
    dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
    employees = dynamodb.create_table(
        TableName="employees",
        KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    audit = dynamodb.create_table(
        TableName="audit",
        KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "audit_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return employees, audit


def event(method, body=None, employee_id=None):
    return {
        "requestContext": {"http": {"method": method}},
        "pathParameters": {"employee_id": employee_id} if employee_id else {},
        "body": json.dumps(body) if body is not None else None,
    }


def test_create_employee_requires_consent_and_writes_audit(monkeypatch):
    with mock_aws():
        install_auth(monkeypatch)
        employees, audit = setup_tables(monkeypatch)
        payload = {
            "employee_id": "EMP001",
            "name": "Asha",
            "email": "asha@example.test",
            "department": "Engineering",
            "shift_start": "09:00",
            "shift_end": "18:00",
            "consent": True,
        }
        result = handler(event("POST", payload), None)
        assert result["statusCode"] == 201
        stored = employees.get_item(Key={"employee_id": "EMP001"})["Item"]
        assert stored["active"] is True
        assert stored["face_ids"] == []
        assert stored["consent_at"]
        assert audit.scan()["Items"][0]["action"] == "employee_create"


def test_create_employee_rejects_missing_consent(monkeypatch):
    with mock_aws():
        install_auth(monkeypatch)
        setup_tables(monkeypatch)
        payload = {
            "employee_id": "EMP001",
            "name": "Asha",
            "email": "asha@example.test",
            "department": "Engineering",
            "shift_start": "09:00",
            "shift_end": "18:00",
            "consent": False,
        }
        result = handler(event("POST", payload), None)
        assert result["statusCode"] == 400


def test_deactivate_keeps_employee_record_and_audits(monkeypatch):
    with mock_aws():
        install_auth(monkeypatch)
        employees, audit = setup_tables(monkeypatch)
        employees.put_item(Item={
            "employee_id": "EMP001",
            "name": "Asha",
            "active": True,
            "face_ids": ["face-1"],
        })
        result = handler(event("DELETE", employee_id="EMP001"), None)
        assert result["statusCode"] == 200
        stored = employees.get_item(Key={"employee_id": "EMP001"})["Item"]
        assert stored["active"] is False
        assert stored["face_ids"] == ["face-1"]
        assert audit.scan()["Items"][0]["action"] == "employee_deactivate"
