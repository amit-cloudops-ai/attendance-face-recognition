"""Moto-backed integration test for the employee API and audit transaction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared/python"))

from services.data.employees import handler


def _admin_event(method: str, *, body: dict | None = None, employee_id: str | None = None) -> dict:
    return {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "cognito:groups": ["admin"],
                        "cognito:username": "integration-admin",
                    }
                }
            },
            "http": {"method": method},
        },
        "pathParameters": {"employee_id": employee_id} if employee_id else {},
        "body": json.dumps(body) if body is not None else None,
    }


@mock_aws
def test_employee_create_duplicate_and_deactivate_are_audited_atomically(monkeypatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("TABLE_EMPLOYEES", "attendance-dev-employees")
    monkeypatch.setenv("TABLE_AUDIT", "attendance-dev-audit")
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    employees = dynamodb.create_table(
        TableName="attendance-dev-employees",
        KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    audit = dynamodb.create_table(
        TableName="attendance-dev-audit",
        KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "audit_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    employees.wait_until_exists()
    audit.wait_until_exists()

    body = {
        "employee_id": "EMP901",
        "name": "Integration Employee",
        "email": "integration@example.test",
        "department": "Engineering",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "consent": True,
    }

    created = handler.lambda_handler(_admin_event("POST", body=body), None)
    assert created["statusCode"] == 201
    public_employee = json.loads(created["body"])
    assert public_employee["employee_id"] == "EMP901"
    assert public_employee["has_face_templates"] is False
    assert "face_ids" not in public_employee

    stored = employees.get_item(Key={"employee_id": "EMP901"}, ConsistentRead=True)["Item"]
    audit_after_create = audit.scan(ConsistentRead=True)["Items"]
    assert stored["active"] is True
    assert stored["consent_at"]
    assert len(audit_after_create) == 1
    assert audit_after_create[0]["action"] == "employee_create"

    duplicate = handler.lambda_handler(_admin_event("POST", body=body), None)
    assert duplicate["statusCode"] == 409
    assert len(audit.scan(ConsistentRead=True)["Items"]) == 1

    deactivated = handler.lambda_handler(
        _admin_event("DELETE", employee_id="EMP901"), None
    )
    assert deactivated["statusCode"] == 200
    assert json.loads(deactivated["body"])["active"] is False
    final_item = employees.get_item(Key={"employee_id": "EMP901"}, ConsistentRead=True)["Item"]
    final_audits = audit.scan(ConsistentRead=True)["Items"]
    assert final_item["active"] is False
    assert {item["action"] for item in final_audits} == {
        "employee_create",
        "employee_deactivate",
    }
