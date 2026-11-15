import json

import boto3
import pytest
from attendance_common import config
from moto import mock_aws

from services.data.daily_job import handler as daily_job
from services.data.reports import handler as reports_handler
from services.data.weekly_job import handler as weekly_job


def admin_event(query=None, group="admin"):
    return {
        "requestContext": {"authorizer": {"jwt": {"claims": {
            "cognito:groups": f"[{group}]",
        }}}},
        "queryStringParameters": query or {},
    }


@pytest.fixture
def job_resources(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
        monkeypatch.setenv("TABLE_CONFIG", "config")
        monkeypatch.setenv("BUCKET_REPORTS", "attendance-reports")
        db = boto3.resource("dynamodb", region_name="us-east-1")
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
        settings = db.create_table(
            TableName="config",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        settings.put_item(Item={"pk": "SETTINGS", "weekend_days": [6, 7]})
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(
            Bucket="attendance-reports",
        )
        sns = boto3.client("sns", region_name="us-east-1")
        topic = sns.create_topic(Name="attendance-alerts")["TopicArn"]
        monkeypatch.setenv("ALERTS_TOPIC_ARN", topic)
        config._reset_cache()
        yield employees, attendance, settings, s3
        config._reset_cache()


def _put_employee(table, employee_id, name):
    table.put_item(Item={
        "employee_id": employee_id, "name": name, "active": True,
        "shift_start": "09:00", "shift_end": "18:00",
    })


def _put_attendance(table, employee_id, day, status, clock_in=None, clock_out=None):
    item = {"employee_id": employee_id, "date": day, "status": status, "source": "face"}
    if clock_in:
        item["clock_in"] = f"{day}T{clock_in}:00+05:30"
    if clock_out:
        item["clock_out"] = f"{day}T{clock_out}:00+05:30"
    table.put_item(Item=item)


def _report(s3, key):
    return json.loads(s3.get_object(Bucket="attendance-reports", Key=key)["Body"].read())


def test_daily_job_marks_absent_and_missing_clockout_idempotently(job_resources):
    employees, attendance, _, s3 = job_resources
    _put_employee(employees, "EMP001", "Priya")
    _put_employee(employees, "EMP002", "Arun")
    _put_employee(employees, "EMP003", "Meera")
    _put_attendance(attendance, "EMP001", "2026-11-13", "present", "09:05")
    _put_attendance(attendance, "EMP002", "2026-11-13", "late", "09:45", "18:00")

    first = daily_job.lambda_handler({"date": "2026-11-13"}, None)
    second = daily_job.lambda_handler({"date": "2026-11-13"}, None)
    assert first["statusCode"] == second["statusCode"] == 200
    report = _report(s3, "reports/daily/2026-11-13.json")
    assert report["totals"] == {
        "employees": 3, "present": 1, "late": 1, "absent": 1, "missing_clock_out": 1,
    }
    rows = {row["employee_id"]: row for row in report["records"]}
    assert rows["EMP003"]["status"] == "absent"
    assert "missing_clock_out" in rows["EMP001"]["flags"]
    stored_missing = attendance.get_item(
        Key={"employee_id": "EMP001", "date": "2026-11-13"}
    )["Item"]
    stored_absent = attendance.get_item(
        Key={"employee_id": "EMP003", "date": "2026-11-13"}
    )["Item"]
    assert stored_missing["version"] == 1
    assert stored_absent["version"] == 1
    csv_text = s3.get_object(
        Bucket="attendance-reports", Key="reports/daily/2026-11-13.csv"
    )["Body"].read().decode()
    assert "EMP003,Meera,2026-11-13,absent" in csv_text


def test_daily_job_skips_weekends_and_holidays(job_resources):
    employees, attendance, settings, s3 = job_resources
    _put_employee(employees, "EMP001", "Priya")
    weekend = daily_job.lambda_handler({"date": "2026-11-14"}, None)
    weekend_report = _report(s3, "reports/daily/2026-11-14.json")
    assert weekend["statusCode"] == 200 and weekend_report["skipped"] == "weekend"
    settings.put_item(Item={"pk": "HOLIDAY#2026-11-13", "name": "Company Holiday"})
    config._reset_cache()
    holiday = daily_job.lambda_handler({"date": "2026-11-13"}, None)
    holiday_report = _report(s3, "reports/daily/2026-11-13.json")
    assert holiday["statusCode"] == 200 and holiday_report["skipped"] == "holiday"
    assert attendance.scan()["Items"] == []


def test_weekly_job_calculates_working_days_and_percentages(job_resources):
    employees, attendance, settings, s3 = job_resources
    _put_employee(employees, "EMP001", "Priya")
    _put_employee(employees, "EMP002", "Arun")
    settings.put_item(Item={"pk": "HOLIDAY#2026-11-11", "name": "Holiday"})
    config._reset_cache()
    _put_attendance(attendance, "EMP001", "2026-11-09", "present", "09:00")
    _put_attendance(attendance, "EMP001", "2026-11-10", "late", "09:40")
    _put_attendance(attendance, "EMP001", "2026-11-12", "absent")
    # Records on holidays and weekends must not affect weekly working-day metrics.
    _put_attendance(attendance, "EMP001", "2026-11-11", "present", "09:00")
    _put_attendance(attendance, "EMP001", "2026-11-14", "present", "09:00")
    _put_attendance(attendance, "EMP001", "2026-11-15", "present", "09:00")
    for day in ["2026-11-09", "2026-11-10", "2026-11-12", "2026-11-13"]:
        _put_attendance(attendance, "EMP002", day, "absent")
    _put_attendance(attendance, "EMP002", "2026-11-11", "absent")
    _put_attendance(attendance, "EMP002", "2026-11-14", "absent")

    result = weekly_job.lambda_handler({"week": "2026-W46"}, None)
    assert result["statusCode"] == 200
    report = _report(s3, "reports/weekly/2026-W46.json")
    assert report["working_days"] == 4
    by_employee = {row["employee_id"]: row for row in report["employees"]}
    assert by_employee["EMP001"]["present_pct"] == 50.0
    assert by_employee["EMP001"]["late_pct"] == 25.0
    assert by_employee["EMP001"]["absent_pct"] == 25.0
    assert report["totals"] == {
        "present_pct": 25.0, "late_pct": 12.5, "absent_pct": 62.5,
    }


def test_weekly_job_zero_working_days_returns_zero_percentages(job_resources):
    employees, _, settings, s3 = job_resources
    _put_employee(employees, "EMP001", "Priya")
    settings.put_item(Item={"pk": "SETTINGS", "weekend_days": [1, 2, 3, 4, 5, 6, 7]})
    config._reset_cache()
    weekly_job.lambda_handler({"week": "2026-W46"}, None)
    report = _report(s3, "reports/weekly/2026-W46.json")
    assert report["working_days"] == 0
    assert report["totals"] == {
        "present_pct": 0.0, "late_pct": 0.0, "absent_pct": 0.0,
    }


def test_reports_returns_summary_and_short_lived_csv_url(job_resources):
    _, _, _, s3 = job_resources
    summary = {"date": "2026-11-13", "totals": {"employees": 2}}
    s3.put_object(
        Bucket="attendance-reports", Key="reports/daily/2026-11-13.json",
        Body=json.dumps(summary).encode(), ContentType="application/json",
    )
    s3.put_object(
        Bucket="attendance-reports", Key="reports/daily/2026-11-13.csv",
        Body=b"employee_id,name\n", ContentType="text/csv",
    )
    response = reports_handler.lambda_handler(admin_event({
        "type": "daily", "period": "2026-11-13",
    }), None)
    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["summary"] == summary
    assert payload["csv_url"].startswith("https://")


def test_reports_validates_period_and_missing_report(job_resources):
    invalid = reports_handler.lambda_handler(admin_event({
        "type": "daily", "period": "2026-02-30",
    }), None)
    missing = reports_handler.lambda_handler(admin_event({
        "type": "weekly", "period": "2026-W99",
    }), None)
    assert invalid["statusCode"] == 400
    assert missing["statusCode"] == 400
    missing = reports_handler.lambda_handler(admin_event({
        "type": "weekly", "period": "2026-W46",
    }), None)
    assert missing["statusCode"] == 404
