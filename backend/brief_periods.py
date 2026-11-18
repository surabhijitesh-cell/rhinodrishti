"""Brief periods follow IST calendar days.

Timestamps come back in UTC because `published_at` is stored in UTC and compared
as text. Ends are exclusive. Date-keyed data (faultline_scores.date) must go
through `period_dates`: slicing an ISO string would give the wrong day.
"""
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def _utc_iso(year: int, month: int, day: int) -> str:
    return datetime(year, month, day, tzinfo=IST).astimezone(timezone.utc).isoformat()


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_range(year: int, month: int) -> tuple[str, str]:
    next_year, next_month = _next_month(year, month)
    return _utc_iso(year, month, 1), _utc_iso(next_year, next_month, 1)


def fortnight_range(year: int, month: int, period: int) -> tuple[str, str, str]:
    """(start, end, label) for period 1 (1st-15th) or 2 (16th-last day)."""
    name = date(year, month, 1).strftime("%B %Y")
    if period == 1:
        return _utc_iso(year, month, 1), _utc_iso(year, month, 16), f"1-15 {name}"
    next_year, next_month = _next_month(year, month)
    last_day = monthrange(year, month)[1]
    return _utc_iso(year, month, 16), _utc_iso(next_year, next_month, 1), f"16-{last_day} {name}"


def period_dates(start_iso: str, end_iso: str) -> tuple[str, str]:
    """First and last IST calendar dates (both inclusive) of a period."""
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).astimezone(IST).date()
    end = datetime.fromisoformat(end_iso.replace("Z", "+00:00")).astimezone(IST).date()
    return start.isoformat(), (end - timedelta(days=1)).isoformat()


def ist_today() -> str:
    return datetime.now(IST).date().isoformat()
