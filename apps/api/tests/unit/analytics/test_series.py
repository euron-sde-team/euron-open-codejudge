"""Analytics helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from codejudge.analytics.service import _rate, _series, bucket_day


def test_missing_days_are_zero() -> None:
    start = date(2026, 10, 1)
    points = _series({date(2026, 10, 2): (5, 2)}, start, date(2026, 10, 3))
    assert [(p.day.day, p.submissions, p.accepted) for p in points] == [
        (1, 0, 0),
        (2, 5, 2),
        (3, 0, 0),
    ]


def test_buckets_are_utc_days() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    assert bucket_day(datetime(2026, 10, 2, 1, 0, tzinfo=ist)) == date(2026, 10, 1)
    assert bucket_day(datetime(2026, 10, 2, 1, 0, tzinfo=UTC)) == date(2026, 10, 2)


def test_rate() -> None:
    assert _rate(2, 3) == 0.6667 and _rate(0, 0) is None
