"""Injectable clock. Business code reads time only through a `Clock` (conventions.md, Code)."""

from datetime import UTC, datetime
from typing import Protocol

from django.utils import timezone


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return timezone.now()


default_clock: Clock = SystemClock()


def to_iso(value: datetime) -> str:
    """ISO 8601 in UTC with `Z` (conventions.md, API)."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
