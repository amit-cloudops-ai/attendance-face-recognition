"""Seed a deterministic demo dataset into the configured dev DynamoDB tables.

Run with TABLE_EMPLOYEES, TABLE_ATTENDANCE and TABLE_CONFIG set to dev table names.
This script never reads or writes real employee data.
"""
from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3

IST = ZoneInfo("Asia/Kolkata")
DEMO_EMPLOYEES = [
    ("DEMO001", "Aarav Sharma", "Engineering"),
    ("DEMO002", "Diya Rao", "Human Resources"),
    ("DEMO003", "Ishaan Kumar", "Finance"),
    ("DEMO004", "Meera Nair", "Operations"),
    ("DEMO005", "Kabir Shah", "Engineering"),
    ("DEMO006", "Anaya Iyer", "Marketing"),
    ("DEMO007", "Vihaan Das", "Support"),
    ("DEMO008", "Saanvi Patel", "Finance"),
    ("DEMO009", "Arjun Menon", "Operations"),
    ("DEMO010", "Aadhya Reddy", "Support"),
]


def _table(resource, env_name):
    name = os.getenv(env_name)
    if not name:
        raise RuntimeError(f"Set {env_name} to a development table name before running")
    if "-prod-" in name or name.endswith("-prod"):
        raise RuntimeError("Refusing to seed a production table")
    return resource.Table(name)


def main():
    if os.getenv("ENV") != "dev":
        raise RuntimeError("Set ENV=dev before running the seed script")
    for variable in ("TABLE_EMPLOYEES", "TABLE_ATTENDANCE", "TABLE_CONFIG"):
        if not os.getenv(variable, "").startswith("attendance-dev-"):
            raise RuntimeError(f"{variable} must point to an attendance-dev-* table")
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    employees = _table(dynamodb, "TABLE_EMPLOYEES")
    attendance = _table(dynamodb, "TABLE_ATTENDANCE")
    config = _table(dynamodb, "TABLE_CONFIG")
    now = datetime.now(IST)
    start = now.date() - timedelta(days=29)

    for index, (employee_id, name, department) in enumerate(DEMO_EMPLOYEES):
        employees.put_item(
            Item={
                "employee_id": employee_id,
                "name": name,
                "email": f"{employee_id.lower()}@example.test",
                "department": department,
                "shift_start": "09:00",
                "shift_end": "18:00",
                "active": True,
                "face_ids": [],
                "photo_count": 0,
                "consent_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        for offset in range(30):
            day = start + timedelta(days=offset)
            # Deterministic variation: absent, late, and present examples.
            pattern = (index + offset) % 11
            if pattern in {0, 7}:
                status = "absent"
                item = {
                    "employee_id": employee_id,
                    "date": day.isoformat(),
                    "status": status,
                    "source": "system",
                    "updated_at": now.isoformat(),
                }
            else:
                status = "late" if pattern in {2, 5} else "present"
                clock_in_time = time(9, 22 if status == "late" else 3)
                clock_in = datetime.combine(day, clock_in_time, tzinfo=IST)
                item = {
                    "employee_id": employee_id,
                    "date": day.isoformat(),
                    "clock_in": clock_in.isoformat(),
                    "status": status,
                    "source": "face",
                    "confidence": Decimal("98.7"),
                    "updated_at": now.isoformat(),
                }
                if pattern not in {3, 8}:
                    item["clock_out"] = datetime.combine(
                        day, time(18, 0), tzinfo=IST
                    ).isoformat()
                else:
                    item["flags"] = {"missing_clock_out"}
            attendance.put_item(Item=item)

    if not config.get_item(Key={"pk": "SETTINGS"}).get("Item"):
        config.put_item(
            Item={
                "pk": "SETTINGS",
                "face_match_threshold": Decimal(95),
                "min_brightness": Decimal(40),
                "min_sharpness": Decimal(40),
                "grace_minutes": 15,
                "debounce_minutes": 10,
                "weekend_days": [6, 7],
                "max_photos_per_employee": 5,
            }
        )
    print(f"Seeded {len(DEMO_EMPLOYEES)} demo employees across 30 calendar days.")


if __name__ == "__main__":
    main()
