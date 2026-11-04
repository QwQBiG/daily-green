"""Date and cadence rules shared by the daily job and year archives."""
from datetime import date, timedelta
import hashlib


def planned_count(day: date) -> int:
    digest = hashlib.sha256(f"daily-green-v1:{day.isoformat()}".encode()).digest()
    return 2 + int.from_bytes(digest[:8], "big") % 5


def days_between(start: date, through: date):
    day = start
    while day <= through:
        yield day
        if day == through:
            break
        day += timedelta(days=1)
