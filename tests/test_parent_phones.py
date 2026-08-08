"""One Parent Phone cell may hold several numbers.

Families often want both parents on the reminder. The sheet keeps a single
Parent Phone column, so the cell is split on separators — but NOT on the single
spaces inside "(678) 780-5797", and never by handing the raw cell to
normalize_phone_number, which would mash two numbers into one 20-digit string
that quietly goes nowhere.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.message_builder import build_messages
from src.roster import build_roster, split_phones
from src.tut_parser import TutEvent, parse_tut_title

TZ = ZoneInfo("America/New_York")

TEACHERS = [["Joseph", "Joseph", "404-555-0102", "TRUE", ""]]


def students(parent_cell, student_phone="(470) 461-4217"):
    return [["Bill Yu", "Bill", student_phone, "", parent_cell, "TRUE", ""]]


def roster_for(parent_cell, student_phone="(470) 461-4217"):
    return build_roster(TEACHERS, students(parent_cell, student_phone), [])


def bill_event():
    summary = ("[TUT] Type: In-Person, Teacher Name: Joseph teacher, "
               "Student Name: Bill Yu, Subject: Math")
    return TutEvent(
        event_id="e1",
        recurring_event_id=None,
        raw_summary=summary,
        start=datetime(2026, 8, 7, 15, 0, tzinfo=TZ),
        end=datetime(2026, 8, 7, 16, 0, tzinfo=TZ),
        html_link="",
        meet_link=None,
        parsed=parse_tut_title(summary),
    )


# ---------- splitting ----------

def test_single_space_inside_a_number_does_not_split_it():
    # The whole feature is worthless if "(678) 780-5797" becomes two entries.
    assert split_phones("(678) 780-5797") == ["(678) 780-5797"]


def test_two_numbers_separated_by_comma():
    assert split_phones("(678) 780-5797, (404) 123-4567") == [
        "(678) 780-5797", "(404) 123-4567"]


def test_other_separators():
    assert split_phones("678-780-5797; 404-123-4567") == ["678-780-5797", "404-123-4567"]
    assert split_phones("678-780-5797 / 404-123-4567") == ["678-780-5797", "404-123-4567"]
    assert split_phones("678-780-5797\n404-123-4567") == ["678-780-5797", "404-123-4567"]
    assert split_phones("678-780-5797   404-123-4567") == ["678-780-5797", "404-123-4567"]


def test_three_numbers():
    assert len(split_phones("111-111-1111, 222-222-2222, 333-333-3333")) == 3


def test_invisible_bidi_marks_from_pasted_numbers_are_dropped():
    # Google Voice wraps numbers in U+202A/U+202C, and copying one carries them
    # along. They survive into the cell invisibly, and the recipient dedupe in
    # message_builder compares raw strings — so a number pasted twice, once with
    # the marks and once without, would text the same person twice.
    assert split_phones("‪(678) 780-5797‬") == ["(678) 780-5797"]
    assert split_phones("(678) 780-5797, (678) 788-0678‬") == [
        "(678) 780-5797", "(678) 788-0678"]


def test_blank_and_messy_cells():
    assert split_phones("") == []
    assert split_phones(None) == []
    assert split_phones("   ") == []
    assert split_phones(",,  ,") == []
    assert split_phones("  (678) 780-5797  ,  ") == ["(678) 780-5797"]


def test_roster_exposes_the_numbers():
    # StudentRow is a frozen dataclass, so the field is a tuple, not a list.
    r = roster_for("(678) 780-5797, (404) 123-4567")
    row = r.match_student("Bill Yu").row
    assert row.parent_phones == ("(678) 780-5797", "(404) 123-4567")


def test_roster_single_parent_still_works():
    r = roster_for("(678) 780-5797")
    assert r.match_student("Bill Yu").row.parent_phones == ("(678) 780-5797",)


# ---------- effect on the outgoing message ----------

def test_both_parents_become_recipients():
    msgs = build_messages([bill_event()], roster_for("(678) 780-5797, (404) 123-4567"))
    g = next(m for m in msgs if m.kind == "student_group")
    assert not g.blocked
    assert g.phones == ["(470) 461-4217", "(678) 780-5797", "(404) 123-4567"]
    assert g.group_mode


def test_parents_only_no_student_phone():
    msgs = build_messages([bill_event()],
                          roster_for("(678) 780-5797, (404) 123-4567", student_phone=""))
    g = next(m for m in msgs if m.kind == "student_group")
    assert not g.blocked
    assert g.phones == ["(678) 780-5797", "(404) 123-4567"]


def test_still_blocked_when_the_cell_is_empty_and_no_student_phone():
    msgs = build_messages([bill_event()], roster_for("", student_phone=""))
    g = next(m for m in msgs if m.kind == "student_group")
    assert g.blocked
    assert "no student or parent phone" in g.block_reasons[0]


def test_single_parent_unchanged():
    msgs = build_messages([bill_event()], roster_for("(678) 780-5797"))
    g = next(m for m in msgs if m.kind == "student_group")
    assert g.phones == ["(470) 461-4217", "(678) 780-5797"]
