"""IST timezone and time parsing helpers."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def to_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(IST).isoformat(timespec="seconds")


def parse_hhmm(value: str) -> time:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("time must use HH:MM format")
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("time must use a valid HH:MM value") from exc
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise ValueError("time must use HH:MM format")
    return parsed
