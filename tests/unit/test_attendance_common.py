from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3
import pytest
from moto import mock_aws

from attendance_common import config
from attendance_common.record_scan import record_scan
from attendance_common.responses import error, ok
from attendance_common.tz import IST, now_ist, parse_hhmm, today_ist, to_iso

UTC = ZoneInfo("UTC")


@pytest.fixture
def aws_tables(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_REGION", "ap-south-1")
        monkeypatch.setenv("TABLE_EMPLOYEES", "employees")
        monkeypatch.setenv("TABLE_ATTENDANCE", "attendance")
        monkeypatch.delenv("TABLE_CONFIG", raising=False)
        config._reset_cache()
        db = boto3.resource("dynamodb", region_name="ap-south-1")
        employees = db.create_table(TableName="employees", KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        attendance = db.create_table(TableName="attendance", KeySchema=[{"AttributeName": "employee_id", "KeyType": "HASH"},
            {"AttributeName": "date", "KeyType": "RANGE"}], AttributeDefinitions=[{"AttributeName": "employee_id", "AttributeType": "S"},
            {"AttributeName": "date", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
        employees.put_item(Item={"employee_id": "EMP001", "name": "Test Employee", "active": True,
                                 "shift_start": "09:00", "shift_end": "18:00"})
        yield employees, attendance
        config._reset_cache()


def scan(at, confidence=98.5):
    return record_scan("EMP001", datetime.fromisoformat(at), confidence)


def test_time_helpers():
    assert parse_hhmm("09:05").isoformat(timespec="minutes") == "09:05"
    assert to_iso(datetime(2026, 11, 14, 3, 30, tzinfo=UTC)) == "2026-11-14T09:00:00+05:30"
    assert now_ist().tzinfo == IST
    assert today_ist() == now_ist().date()
    for bad in ("9:05", "24:00", "12:60", "12:00:01", None):
        with pytest.raises(ValueError):
            parse_hhmm(bad)
    with pytest.raises(ValueError):
        to_iso(datetime(2026, 11, 14, 9, 0))


def test_response_envelopes():
    import json
    assert ok({"x": 1})["statusCode"] == 200
    failure = error(404, "not_found", "Missing")
    assert failure["statusCode"] == 404
    assert json.loads(failure["body"]) == {"error": {"code": "not_found", "message": "Missing"}}


def test_first_scan_creates_present_clock_in(aws_tables):
    _, table = aws_tables
    result = scan("2026-11-14T09:10:00+05:30")
    assert result == {"action": "clock_in", "status": "present", "date": "2026-11-14",
                      "clock_in": "2026-11-14T09:10:00+05:30", "clock_out": None}
    item = table.get_item(Key={"employee_id": "EMP001", "date": "2026-11-14"})["Item"]
    assert item["confidence"] == Decimal("98.5") and item["source"] == "face"


def test_late_boundary_is_strictly_after_shift_plus_grace(aws_tables):
    assert scan("2026-11-14T09:15:00+05:30")["status"] == "present"
    # Different business date so this is an independent first scan.
    assert scan("2026-11-15T09:16:00+05:30")["status"] == "late"


def test_duplicate_inside_debounce_does_not_write_clock_out(aws_tables):
    first = scan("2026-11-14T09:00:00+05:30")
    second = scan("2026-11-14T09:09:59+05:30")
    assert first["action"] == "clock_in" and second["action"] == "duplicate_ignored"
    assert second["clock_in"] == first["clock_in"] and second["clock_out"] is None


def test_scan_at_debounce_boundary_sets_clock_out(aws_tables):
    scan("2026-11-14T09:00:00+05:30")
    result = scan("2026-11-14T09:10:00+05:30")
    assert result["action"] == "clock_out" and result["clock_out"] == "2026-11-14T09:10:00+05:30"


def test_later_scan_updates_clock_out_and_out_of_order_event_cannot_reverse_it(aws_tables):
    scan("2026-11-14T09:00:00+05:30")
    scan("2026-11-14T09:10:00+05:30")
    latest = scan("2026-11-14T17:30:00+05:30")
    stale = scan("2026-11-14T12:00:00+05:30")
    assert latest["clock_out"] == "2026-11-14T17:30:00+05:30"
    assert stale["clock_out"] == latest["clock_out"]


def test_business_date_uses_ist_after_offset_conversion(aws_tables):
    result = scan("2026-11-13T20:00:00+00:00")
    assert result["date"] == "2026-11-14"
    assert result["clock_in"] == "2026-11-14T01:30:00+05:30"


def test_absent_row_is_conditionally_promoted_to_clock_in(aws_tables):
    _, table = aws_tables
    table.put_item(Item={"employee_id": "EMP001", "date": "2026-11-14", "status": "absent",
                         "flags": {"missing_clock_out"}, "source": "system", "updated_at": "2026-11-14T23:59:00+05:30"})
    result = scan("2026-11-14T09:05:00+05:30")
    item = table.get_item(Key={"employee_id": "EMP001", "date": "2026-11-14"})["Item"]
    assert result["action"] == "clock_in" and item["status"] == "present"
    assert "flags" not in item


def test_inactive_and_unknown_employees_do_not_create_attendance(aws_tables):
    employees, table = aws_tables
    employees.update_item(Key={"employee_id": "EMP001"}, UpdateExpression="SET active=:v", ExpressionAttributeValues={":v": False})
    with pytest.raises(ValueError, match="inactive"):
        scan("2026-11-14T09:00:00+05:30")
    with pytest.raises(ValueError, match="does not exist"):
        record_scan("EMP999", datetime.fromisoformat("2026-11-14T09:00:00+05:30"), 98)
    assert table.scan()["Items"] == []


@pytest.mark.parametrize("employee_id,confidence,stamp", [("", 98, "2026-11-14T09:00:00+05:30"),
    ("EMP001", -1, "2026-11-14T09:00:00+05:30"), ("EMP001", 101, "2026-11-14T09:00:00+05:30"),
    ("EMP001", 98, "2026-11-14T09:00:00")])
def test_invalid_inputs_are_rejected(aws_tables, employee_id, confidence, stamp):
    with pytest.raises(ValueError):
        record_scan(employee_id, datetime.fromisoformat(stamp), confidence)


def test_settings_defaults_are_filled_in(monkeypatch):
    monkeypatch.delenv("TABLE_CONFIG", raising=False)
    config._reset_cache()
    settings = config.get_settings()
    assert settings["grace_minutes"] == 15 and settings["debounce_minutes"] == 10
    assert settings["weekend_days"] == [6, 7]
    config._reset_cache()
