from datetime import date

import pytest

from src.coverage_window import coverage_days, default_span, resolve_window

# 2026-07-27 is a Monday, 2026-08-01 a Saturday, 2026-08-02 a Sunday.
SATURDAY = date(2026, 8, 1)
FRIDAY = date(2026, 7, 31)
SUNDAY = date(2026, 8, 2)
MONDAY = date(2026, 8, 3)
TUESDAY = date(2026, 8, 4)


def test_saturday_covers_three_days():
    assert default_span(SATURDAY) == 3


@pytest.mark.parametrize("day", [
    date(2026, 7, 27),  # Mon
    date(2026, 7, 28),  # Tue
    date(2026, 7, 29),  # Wed
    date(2026, 7, 30),  # Thu
    FRIDAY,
    SUNDAY,
])
def test_other_weekdays_cover_one_day(day):
    assert default_span(day) == 1


def test_coverage_days_are_consecutive():
    assert coverage_days(SUNDAY, 3) == [SUNDAY, MONDAY, TUESDAY]


def test_coverage_days_of_one():
    assert coverage_days(SUNDAY, 1) == [SUNDAY]


@pytest.mark.parametrize("span", [0, -3])
def test_span_below_one_still_returns_one_day(span):
    assert coverage_days(SUNDAY, span) == [SUNDAY]


def test_saturday_run_with_no_params_covers_sunday_through_tuesday():
    first_day, span = resolve_window(None, None, SATURDAY)
    assert (first_day, span) == (SUNDAY, 3)
    assert coverage_days(first_day, span) == [SUNDAY, MONDAY, TUESDAY]


def test_weekday_run_with_no_params_covers_tomorrow_only():
    assert resolve_window(None, None, FRIDAY) == (SATURDAY, 1)


def test_explicit_date_covers_that_day_only_even_on_saturday():
    assert resolve_window("2026-08-03", None, SATURDAY) == (MONDAY, 1)


def test_days_param_wins_over_explicit_date():
    assert resolve_window("2026-08-02", "3", SATURDAY) == (SUNDAY, 3)


def test_unparsable_params_fall_back_to_defaults():
    assert resolve_window("not-a-date", "abc", SATURDAY) == (SUNDAY, 3)


@pytest.mark.parametrize("raw_days, expected", [("99", 7), ("0", 1), ("-2", 1)])
def test_days_param_is_clamped(raw_days, expected):
    assert resolve_window(None, raw_days, FRIDAY)[1] == expected
