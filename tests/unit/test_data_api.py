import json

import boto3
import pytest
from moto import mock_aws

from services.data.attendance_query import handler as attendance_query
from services.data.employees import handler as employees_handler


def admin_event(method="GET", body=None, employee_id=None, query=None, group="admin"):
    return {
        "requestContext": {
            "authorizer": {"jwt": {"claims": {
                "cognito:groups": f"[{group}]",
                "cognito:username": "hr-admin",
            }}},
            "http": {"method": method},
        },
        "pathParameters": {"employee_id": employee_id} if employee_id else {},
        "queryStringParameters": query or {},
        "body": json.dumps(body) if body is not None else None,
    }


@pytest.fixture
def data_tables(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "ap-south-1")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_AUDIT", "audit")
        monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
        db = boto3.resource("dynamodb", region_name="ap-south-1")
        employee_table = db.create_table(
            TableName="employees",
            KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        audit_table = db.create_table(
            TableName="audit",
            KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "audit_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        attendance_table = db.create_table(
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
        yield employee_table, audit_table, attendance_table


def employee_payload(employee_id="EMP001", consent=True):
    return {
        "employee_id": employee_id,
        "name": "Priya Rao",
        "email": "priya@example.com",
        "department": "Operations",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "consent": consent,
    }


def test_employee_routes_require_admin(data_tables):
    denied = employees_handler.lambda_handler(admin_event(group="kiosk"), None)
    assert denied["statusCode"] == 403
    denied = attendance_query.lambda_handler(admin_event(group="kiosk"), None)
    assert denied["statusCode"] == 403


def test_employee_create_requires_consent_and_valid_shift(data_tables):
    assert employees_handler.lambda_handler(
        admin_event("POST", employee_payload(consent=False)), None
    )["statusCode"] == 400
    invalid = employee_payload()
    invalid["shift_start"] = "9am"
    assert employees_handler.lambda_handler(
        admin_event("POST", invalid), None
    )["statusCode"] == 400


def test_employee_create_persists_consent_and_audits(data_tables):
    _, audit, _ = data_tables
    response = employees_handler.lambda_handler(
        admin_event("POST", employee_payload()), None
    )
    assert response["statusCode"] == 201
    item = json.loads(response["body"])
    assert item["active"] is True
    assert item["consent_at"].endswith("+05:30")
    assert item["photo_count"] == 0
    assert "face_ids" not in item
    audit_item = audit.scan()["Items"][0]
    assert audit_item["action"] == "employee_create"
    assert audit_item["actor"] == "hr-admin"


def test_employee_duplicate_get_and_list(data_tables):
    employees_handler.lambda_handler(admin_event("POST", employee_payload()), None)
    duplicate = employees_handler.lambda_handler(
        admin_event("POST", employee_payload()), None
    )
    assert duplicate["statusCode"] == 409
    detail = employees_handler.lambda_handler(
        admin_event("GET", employee_id="EMP001"), None
    )
    assert json.loads(detail["body"])["name"] == "Priya Rao"
    listing = employees_handler.lambda_handler(admin_event(), None)
    assert len(json.loads(listing["body"])["items"]) == 1


def test_employee_deactivate_keeps_record_and_audits(data_tables):
    employees_handler.lambda_handler(admin_event("POST", employee_payload()), None)
    response = employees_handler.lambda_handler(
        admin_event("DELETE", employee_id="EMP001"), None
    )
    item = json.loads(response["body"])
    assert item["active"] is False
    assert item["employee_id"] == "EMP001"
    audit = data_tables[1].scan()["Items"]
    assert any(row["action"] == "employee_deactivate" for row in audit)


def test_attendance_query_by_employee_with_status_and_cursor(data_tables):
    employees, _, attendance = data_tables
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya"})
    for day in ["2026-11-12", "2026-11-13", "2026-11-14"]:
        item = {
            "employee_id": "EMP001", "date": day, "status": "present",
            "clock_in": f"{day}T09:00:00+05:30", "source": "face",
        }
        if day.endswith("14"):
            item["flags"] = {"missing_clock_out"}
        attendance.put_item(Item=item)
    first = attendance_query.lambda_handler(admin_event(query={
        "employee_id": "EMP001", "from": "2026-11-12", "to": "2026-11-14",
        "limit": "2", "status": "present",
    }), None)
    payload = json.loads(first["body"])
    assert len(payload["items"]) == 2
    assert payload["next_cursor"]
    assert payload["items"][0]["name"] == "Priya"
    second = attendance_query.lambda_handler(admin_event(query={
        "employee_id": "EMP001", "from": "2026-11-12", "to": "2026-11-14",
        "limit": "2", "status": "present", "cursor": payload["next_cursor"],
    }), None)
    assert len(json.loads(second["body"])["items"]) == 1


def test_attendance_query_by_date_index_and_multi_day_cursor(data_tables):
    employees, _, attendance = data_tables
    employees.put_item(Item={"employee_id": "EMP001", "name": "Priya"})
    employees.put_item(Item={"employee_id": "EMP002", "name": "Arun"})
    for employee_id, day in [
        ("EMP001", "2026-11-14"),
        ("EMP002", "2026-11-14"),
        ("EMP001", "2026-11-15"),
    ]:
        attendance.put_item(Item={
            "employee_id": employee_id, "date": day, "status": "present", "source": "face"
        })
    first = attendance_query.lambda_handler(admin_event(query={
        "from": "2026-11-14", "to": "2026-11-15", "limit": "2",
    }), None)
    payload = json.loads(first["body"])
    assert len(payload["items"]) == 2
    assert payload["next_cursor"]
    second = attendance_query.lambda_handler(admin_event(query={
        "from": "2026-11-14", "to": "2026-11-15", "limit": "2",
        "cursor": payload["next_cursor"],
    }), None)
    assert len(json.loads(second["body"])["items"]) == 1


@pytest.mark.parametrize("query", [
    {"status": "unknown"},
    {"from": "2026-11-15", "to": "2026-11-14"},
    {"limit": "0", "employee_id": "EMP001"},
    {"from": "not-a-date"},
    {"cursor": "bad", "employee_id": "EMP001"},
    {},
])
def test_attendance_query_rejects_invalid_filters(data_tables, query):
    response = attendance_query.lambda_handler(admin_event(query=query), None)
    assert response["statusCode"] == 400
