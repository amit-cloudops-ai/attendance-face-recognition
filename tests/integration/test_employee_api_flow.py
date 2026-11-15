"""AWS SDK contract integration for employee API DynamoDB transactions."""
from __future__ import annotations

import json

import boto3
from botocore.exceptions import ClientError
from botocore.stub import Stubber

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


def test_employee_api_uses_atomic_dynamodb_transactions_and_hides_face_ids(monkeypatch) -> None:
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("TABLE_EMPLOYEES", "attendance-dev-employees")
    monkeypatch.setenv("TABLE_AUDIT", "attendance-dev-audit")
    resource = boto3.resource(
        "dynamodb",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    client = resource.meta.client
    monkeypatch.setattr(boto3, "resource", lambda service_name, **kwargs: resource)

    captured_transactions: list[dict] = []

    def capture_transaction(params, **kwargs) -> None:
        captured_transactions.append(params)

    client.meta.events.register(
        "before-parameter-build.dynamodb.TransactWriteItems",
        capture_transaction,
    )

    original_transact_write_items = client.transact_write_items
    transaction_call_count = 0

    def transact_write_items(**kwargs):
        nonlocal transaction_call_count
        transaction_call_count += 1
        if transaction_call_count == 2:
            capture_transaction(kwargs)
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed", "Message": "Employee already exists"},
                        {"Code": "None"},
                    ],
                },
                "TransactWriteItems",
            )
        return original_transact_write_items(**kwargs)

    monkeypatch.setattr(client, "transact_write_items", transact_write_items)

    existing_item = {
        "employee_id": {"S": "EMP901"},
        "name": {"S": "Integration Employee"},
        "email": {"S": "integration@example.test"},
        "department": {"S": "Engineering"},
        "shift_start": {"S": "09:00"},
        "shift_end": {"S": "18:00"},
        "active": {"BOOL": True},
        "face_ids": {"L": [{"S": "face-template-id"}]},
        "photo_count": {"N": "1"},
        "consent_at": {"S": "2026-11-15T09:00:00+05:30"},
        "created_at": {"S": "2026-11-15T09:00:00+05:30"},
        "updated_at": {"S": "2026-11-15T09:00:00+05:30"},
    }

    body = {
        "employee_id": "EMP901",
        "name": "Integration Employee",
        "email": "integration@example.test",
        "department": "Engineering",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "consent": True,
    }

    with Stubber(client) as stubber:
        stubber.add_response("transact_write_items", {})
        stubber.add_response(
            "get_item",
            {"Item": existing_item},
            expected_params={
                "TableName": "attendance-dev-employees",
                "Key": {"employee_id": "EMP901"},
                "ConsistentRead": True,
            },
        )
        stubber.add_response(
            "get_item",
            {"Item": existing_item},
            expected_params={
                "TableName": "attendance-dev-employees",
                "Key": {"employee_id": "EMP901"},
                "ConsistentRead": True,
            },
        )
        stubber.add_response("transact_write_items", {})

        created = handler.lambda_handler(_admin_event("POST", body=body), None)
        duplicate = handler.lambda_handler(_admin_event("POST", body=body), None)
        deactivated = handler.lambda_handler(
            _admin_event("DELETE", employee_id="EMP901"), None
        )

    assert created["statusCode"] == 201, created
    created_employee = json.loads(created["body"])
    assert created_employee["employee_id"] == "EMP901"
    assert created_employee["has_face_templates"] is False
    assert "face_ids" not in created_employee

    assert duplicate["statusCode"] == 409
    assert deactivated["statusCode"] == 200
    deactivated_employee = json.loads(deactivated["body"])
    assert deactivated_employee["active"] is False
    assert deactivated_employee["has_face_templates"] is True
    assert "face_ids" not in deactivated_employee

    assert len(captured_transactions) == 3
    create_items = captured_transactions[0]["TransactItems"]
    assert create_items[0]["Put"]["TableName"] == "attendance-dev-employees"
    assert create_items[0]["Put"]["ConditionExpression"] == "attribute_not_exists(employee_id)"
    assert create_items[1]["Put"]["TableName"] == "attendance-dev-audit"
    assert create_items[1]["Put"]["Item"]["action"] == {"S": "employee_create"}

    duplicate_items = captured_transactions[1]["TransactItems"]
    assert duplicate_items[0]["Put"]["ConditionExpression"] == "attribute_not_exists(employee_id)"

    deactivate_items = captured_transactions[2]["TransactItems"]
    assert deactivate_items[0]["Update"]["TableName"] == "attendance-dev-employees"
    assert deactivate_items[0]["Update"]["ConditionExpression"] == "active=:active"
    assert deactivate_items[1]["Put"]["TableName"] == "attendance-dev-audit"
    assert deactivate_items[1]["Put"]["Item"]["action"] == {"S": "employee_deactivate"}
