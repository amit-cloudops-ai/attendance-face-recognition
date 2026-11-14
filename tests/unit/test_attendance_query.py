import json
import sys
import types

import boto3
from moto import mock_aws

from services.data.attendance_query.handler import handler


def install_auth(monkeypatch):
    auth = types.ModuleType("attendance_common.auth")
    auth.require_group = lambda event, group: True
    auth.get_username = lambda event: "test-admin"
    monkeypatch.setitem(sys.modules, "attendance_common.auth", auth)


def setup_tables(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
    monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
    dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
    employees = dynamodb.create_table(
        TableName="employees",
        KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    attendance = dynamodb.create_table(
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
    for employee_id, name in (("EMP001", "Asha"), ("EMP002", "Ravi")):
        employees.put_item(Item={"employee_id": employee_id, "name": name})
    attendance.put_item(Item={
        "employee_id": "EMP001", "date": "2026-11-09",
        "status": "absent", "source": "system",
    })
    attendance.put_item(Item={
        "employee_id": "EMP002", "date": "2026-11-09",
        "status": "present", "source": "face",
        "clock_in": "2026-11-09T09:00:00+05:30",
    })
    return attendance


def query_event(params):
    return {
        "requestContext": {"http": {"method": "GET"}},
        "queryStringParameters": params,
    }


def test_status_filter_continues_past_filtered_page(monkeypatch):
    with mock_aws():
        install_auth(monkeypatch)
        setup_tables(monkeypatch)
        result = handler(query_event({
            "from": "2026-11-09",
            "to": "2026-11-09",
            "status": "present",
            "limit": "1",
        }), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["items"]) == 1
        assert body["items"][0]["employee_id"] == "EMP002"
        assert body["items"][0]["name"] == "Ravi"


def test_attendance_query_paginates(monkeypatch):
    with mock_aws():
        install_auth(monkeypatch)
        setup_tables(monkeypatch)
        first = handler(query_event({
            "from": "2026-11-09",
            "to": "2026-11-09",
            "limit": "1",
        }), None)
        first_body = json.loads(first["body"])
        assert len(first_body["items"]) == 1
        assert first_body["next_cursor"]

        second = handler(query_event({
            "from": "2026-11-09",
            "to": "2026-11-09",
            "limit": "1",
            "cursor": first_body["next_cursor"],
        }), None)
        second_body = json.loads(second["body"])
        assert len(second_body["items"]) == 1
        assert second_body["items"][0]["employee_id"] != first_body["items"][0]["employee_id"]


def test_employee_partition_date_range_query(monkeypatch):
    with mock_aws():
        install_auth(monkeypatch)
        attendance = setup_tables(monkeypatch)
        attendance.put_item(Item={
            "employee_id": "EMP001", "date": "2026-11-10",
            "status": "late", "source": "face",
        })
        result = handler(query_event({
            "employee_id": "EMP001",
            "from": "2026-11-09",
            "to": "2026-11-10",
        }), None)
        body = json.loads(result["body"])
        assert {item["date"] for item in body["items"]} == {"2026-11-09", "2026-11-10"}
