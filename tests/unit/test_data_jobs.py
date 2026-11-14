from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
import pytest
from moto import mock_aws

from services.data.daily_job.handler import handler as daily_handler
from services.data.weekly_job.handler import handler as weekly_handler

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def aws_data(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
    monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
    monkeypatch.setenv("TABLE_CONFIG", "config")
    monkeypatch.setenv("BUCKET_REPORTS", "attendance-test-reports")

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
        config = dynamodb.create_table(
            TableName="config",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        config.put_item(Item={
            "pk": "SETTINGS",
            "weekend_days": [6, 7],
            "grace_minutes": 15,
            "debounce_minutes": 10,
        })
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="attendance-test-reports",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        yield employees, attendance, config, s3


def add_employee(table, employee_id="EMP001", name="Test Employee"):
    table.put_item(Item={
        "employee_id": employee_id,
        "name": name,
        "active": True,
        "shift_start": "09:00",
        "shift_end": "18:00",
    })


def test_daily_job_marks_absences_and_flags_missing_clock_out(aws_data):
    employees, attendance, _, s3 = aws_data
    add_employee(employees, "EMP001", "Clocked In")
    add_employee(employees, "EMP002", "No Scan")
    attendance.put_item(Item={
        "employee_id": "EMP001",
        "date": "2026-11-09",
        "clock_in": datetime(2026, 11, 9, 9, 0, tzinfo=IST).isoformat(),
        "status": "present",
        "source": "face",
        "updated_at": datetime(2026, 11, 9, 9, 0, tzinfo=IST).isoformat(),
    })

    result = daily_handler({"date": "2026-11-09"}, None)
    assert result["totals"]["employees"] == 2
    assert result["totals"]["absent"] == 1
    assert result["totals"]["missing_clock_out"] == 1

    clocked_in = attendance.get_item(Key={"employee_id": "EMP001", "date": "2026-11-09"})["Item"]
    absent = attendance.get_item(Key={"employee_id": "EMP002", "date": "2026-11-09"})["Item"]
    assert "missing_clock_out" in clocked_in["flags"]
    assert absent["status"] == "absent"
    report = s3.get_object(Bucket="attendance-test-reports", Key="reports/daily/2026-11-09.json")
    assert b'"date": "2026-11-09"' in report["Body"].read()


def test_daily_job_rerun_does_not_overwrite_existing_attendance(aws_data):
    employees, attendance, _, _ = aws_data
    add_employee(employees)
    original = {
        "employee_id": "EMP001",
        "date": "2026-11-09",
        "status": "late",
        "clock_in": "2026-11-09T09:30:00+05:30",
        "source": "face",
        "updated_at": "2026-11-09T09:30:00+05:30",
    }
    attendance.put_item(Item=original)
    daily_handler({"date": "2026-11-09"}, None)
    stored = attendance.get_item(Key={"employee_id": "EMP001", "date": "2026-11-09"})["Item"]
    assert stored["status"] == "late"
    assert stored["clock_in"] == original["clock_in"]


def test_daily_job_skips_weekends_and_holidays(aws_data):
    employees, _, config, s3 = aws_data
    add_employee(employees)
    weekend = daily_handler({"date": "2026-11-14"}, None)
    assert weekend["skipped"] == "weekend"

    config.put_item(Item={"pk": "HOLIDAY#2026-11-09", "name": "Demo Holiday"})
    holiday = daily_handler({"date": "2026-11-09"}, None)
    assert holiday["skipped"] == "holiday"
    report = s3.get_object(Bucket="attendance-test-reports", Key="reports/daily/2026-11-09.json")
    assert b'"skipped": "holiday"' in report["Body"].read()


def test_weekly_job_calculates_percentages_and_excludes_holiday(aws_data):
    employees, attendance, config, s3 = aws_data
    add_employee(employees)
    config.put_item(Item={"pk": "HOLIDAY#2026-11-10", "name": "Demo Holiday"})
    rows = [
        ("2026-11-09", "present"),
        ("2026-11-11", "late"),
        ("2026-11-12", "absent"),
        ("2026-11-13", "present"),
    ]
    for day, status in rows:
        item = {
            "employee_id": "EMP001",
            "date": day,
            "status": status,
            "source": "system" if status == "absent" else "face",
            "updated_at": f"{day}T18:00:00+05:30",
        }
        if status != "absent":
            item["clock_in"] = f"{day}T09:00:00+05:30"
        attendance.put_item(Item=item)

    result = weekly_handler({"week": "2026-W46"}, None)
    assert result["working_days"] == 4
    summary = s3.get_object(
        Bucket="attendance-test-reports",
        Key="reports/weekly/2026-W46.json",
    )
    body = __import__("json").loads(summary["Body"].read())
    employee = body["employees"][0]
    assert employee["present_days"] == 3
    assert employee["late_days"] == 1
    assert employee["absent_days"] == 1
    assert employee["present_pct"] == 75.0
    assert employee["late_pct"] == 25.0
    assert employee["absent_pct"] == 25.0


def test_weekly_job_handles_zero_working_days(aws_data):
    employees, _, config, s3 = aws_data
    add_employee(employees)
    config.put_item(Item={
        "pk": "SETTINGS",
        "weekend_days": [1, 2, 3, 4, 5, 6, 7],
    })
    result = weekly_handler({"week": "2026-W46"}, None)
    assert result["working_days"] == 0
    report = s3.get_object(
        Bucket="attendance-test-reports",
        Key="reports/weekly/2026-W46.json",
    )
    body = __import__("json").loads(report["Body"].read())
    assert body["employees"][0]["present_pct"] == 0.0
    assert body["totals"]["absent_pct"] == 0.0
