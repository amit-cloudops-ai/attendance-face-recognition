from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
import pytest
from attendance_common.record_scan import record_scan
from moto import mock_aws

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def attendance_tables(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
    monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
    monkeypatch.setenv("TABLE_CONFIG", "config")

    with mock_aws():
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
            BillingMode="PAY_PER_REQUEST",
        )
        config = dynamodb.create_table(
            TableName="config",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        employees.put_item(
            Item={
                "employee_id": "EMP001",
                "name": "Test Employee",
                "shift_start": "09:00",
                "active": True,
            }
        )
        config.put_item(
            Item={"pk": "SETTINGS", "grace_minutes": 15, "debounce_minutes": 10}
        )
        yield employees, attendance, config


def scan(hour, minute=0, day=14):
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


def test_first_scan_is_present(attendance_tables):
    result = record_scan("EMP001", scan(9, 10), 98.5)
    assert result["action"] == "clock_in"
    assert result["status"] == "present"
    assert result["clock_out"] is None


def test_first_scan_after_grace_is_late(attendance_tables):
    result = record_scan("EMP001", scan(9, 16), 98.5)
    assert result["action"] == "clock_in"
    assert result["status"] == "late"


def test_scan_inside_debounce_is_ignored(attendance_tables):
    record_scan("EMP001", scan(9, 0), 98.0)
    result = record_scan("EMP001", scan(9, 5), 97.0)
    assert result["action"] == "duplicate_ignored"
    assert result["clock_out"] is None


def test_scan_after_debounce_is_clock_out(attendance_tables):
    record_scan("EMP001", scan(9, 0), 98.0)
    result = record_scan("EMP001", scan(17, 30), 97.0)
    assert result["action"] == "clock_out"
    assert result["clock_out"] == scan(17, 30).isoformat()


def test_absent_row_is_converted_to_clock_in(attendance_tables):
    _, attendance, _ = attendance_tables
    attendance.put_item(
        Item={
            "employee_id": "EMP001",
            "date": "2026-11-14",
            "status": "absent",
            "source": "system",
            "updated_at": scan(23, 59).isoformat(),
        }
    )
    result = record_scan("EMP001", scan(9, 5), 99.0)
    assert result["action"] == "clock_in"
    assert result["status"] == "present"
    assert result["clock_in"] == scan(9, 5).isoformat()


def test_date_is_derived_in_ist(attendance_tables):
    utc_time = datetime.fromisoformat("2026-11-14T18:45:00+00:00")
    result = record_scan("EMP001", utc_time, 99.0)
    assert result["date"] == "2026-11-15"


def test_unknown_employee_is_rejected(attendance_tables):
    with pytest.raises(ValueError, match="Unknown employee"):
        record_scan("EMP999", scan(9, 0), 98.0)


def test_inactive_employee_is_rejected(attendance_tables):
    employees, _, _ = attendance_tables
    employees.update_item(
        Key={"employee_id": "EMP001"},
        UpdateExpression="SET active = :false",
        ExpressionAttributeValues={":false": False},
    )
    with pytest.raises(ValueError, match="Inactive employee"):
        record_scan("EMP001", scan(9, 0), 98.0)
