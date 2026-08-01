"""Which dates one run of the reminder app covers. Pure logic, no I/O."""

from __future__ import annotations

from datetime import date, timedelta

SATURDAY = 5      # date.weekday(): Mon=0 … Sat=5, Sun=6
MAX_SPAN = 7

# A Saturday run reaches Sunday, Monday and Tuesday, so the weekend sitting
# prepares the start of the week in one go. Every other day covers tomorrow,
# which is what the daily 2pm task has always done.
SATURDAY_SPAN = 3


def default_span(today: date) -> int:
    """How many days a run started on `today` should cover."""
    return SATURDAY_SPAN if today.weekday() == SATURDAY else 1


def coverage_days(first_day: date, span: int) -> list[date]:
    """`span` consecutive dates starting at `first_day`. Never fewer than one."""
    return [first_day + timedelta(days=i) for i in range(max(1, span))]


def resolve_window(raw_date, raw_days, today: date) -> tuple[date, int]:
    """Turn the ?date= / ?days= query params into (first_day, span).

    Precedence, first match wins:
      1. ?days=N sets the span, even alongside ?date=
      2. ?date= alone means that single day
      3. neither -> tomorrow, for default_span(today) days

    Unparsable values are treated as absent rather than raising, so a typo in
    the address bar degrades to the normal view instead of an error page.
    """
    explicit_day = None
    if raw_date:
        try:
            explicit_day = date.fromisoformat(str(raw_date))
        except ValueError:
            explicit_day = None

    span = None
    if raw_days:
        try:
            span = max(1, min(MAX_SPAN, int(str(raw_days))))
        except ValueError:
            span = None

    first_day = explicit_day or (today + timedelta(days=1))
    if span is None:
        span = 1 if explicit_day else default_span(today)
    return first_day, span
