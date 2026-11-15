"""Time helpers: everything is stored in UTC; days are the patient's local calendar day."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import iso_utc, to_utc

__all__ = ["iso_utc", "to_utc", "now_utc", "now_iso", "parse_iso", "local_day_bounds"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return iso_utc(now_utc())


def parse_iso(text: str) -> datetime:
    """Parse an ISO-8601 string (with `Z`, an offset, or no zone = UTC) to aware UTC."""
    return to_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))


def local_day_bounds(day: date, tz: str) -> tuple[datetime, datetime]:
    """[local midnight, next local midnight) of `day` in `tz`, as aware UTC datetimes."""
    zone = ZoneInfo(tz)
    start = datetime.combine(day, time.min, zone)
    end = datetime.combine(day + timedelta(days=1), time.min, zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
