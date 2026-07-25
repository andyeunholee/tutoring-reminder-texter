from datetime import datetime
from zoneinfo import ZoneInfo

from src.message_builder import build_messages
from src.roster import build_roster
from src.tut_parser import TutEvent, parse_tut_title

TZ = ZoneInfo("America/New_York")

TEACHERS = [
    ["Joseph", "Joseph", "404-555-0102", "TRUE", ""],
    ["Jeongbeen", "Jeongbeen", "404-555-0101", "TRUE", ""],
]
STUDENTS = [
    ["Kyuheon (Andrew) Ahn", "Andrew", "404-555-0202", "Mrs. Ahn", "404-555-0203", "TRUE", ""],
    ["Jian Choi", "", "", "Mrs. Choi", "404-555-0205", "TRUE", ""],
    ["MinYeong Park", "MinYeong", "404-555-0301", "", "404-555-0302", "TRUE", ""],
    ["Buhyeon Park", "Buhyeon", "404-555-0303", "", "404-555-0302", "TRUE", ""],
]


def make_event(summary, hour, eid="e1"):
    return TutEvent(
        event_id=eid,
        recurring_event_id=None,
        raw_summary=summary,
        start=datetime(2026, 8, 1, hour, 0, tzinfo=TZ),
        end=datetime(2026, 8, 1, hour + 2, 0, tzinfo=TZ),
        html_link="",
        meet_link=None,
        parsed=parse_tut_title(summary),
    )


def roster():
    return build_roster(TEACHERS, STUDENTS, [["MinYeong", "student", "MinYeong Park"], ["Buhyeon", "student", "Buhyeon Park"]])


def test_single_event_produces_teacher_and_group():
    ev = make_event(" [TUT] Type: In-Person (Room #1), Teacher Name: Joseph teacher, Student Name: Kyuheon (Andrew) Ahn, Subject: English", 13)
    msgs = build_messages([ev], roster())
    kinds = {m.kind for m in msgs}
    assert kinds == {"teacher", "student_group"}
    t = next(m for m in msgs if m.kind == "teacher")
    assert not t.blocked
    assert t.phones == ["404-555-0102"]
    assert not t.group_mode
    g = next(m for m in msgs if m.kind == "student_group")
    assert sorted(g.phones) == ["404-555-0202", "404-555-0203"]
    assert g.group_mode
    assert "Andrew" in g.body
    assert "Saturday, August 1" in g.body


def test_teacher_two_sessions_merged():
    ev1 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Kyuheon (Andrew) Ahn, Subject: English", 13, "e1")
    ev2 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15, "e2")
    msgs = build_messages([ev1, ev2], roster())
    teachers = [m for m in msgs if m.kind == "teacher"]
    assert len(teachers) == 1
    assert "2 sessions" in teachers[0].body
    assert "1:00 PM" in teachers[0].body and "3:00 PM" in teachers[0].body


def test_no_merge_toggle():
    ev1 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Kyuheon (Andrew) Ahn, Subject: English", 13, "e1")
    ev2 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15, "e2")
    msgs = build_messages([ev1, ev2], roster(), merge_sessions_per_recipient=False)
    teachers = [m for m in msgs if m.kind == "teacher"]
    assert len(teachers) == 2


def test_cancelled_excluded_by_default():
    ev = make_event("canceled by student: [TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 13)
    assert build_messages([ev], roster()) == []
    included = build_messages([ev], roster(), include_cancelled=True)
    assert len(included) == 2
    assert all(m.is_cancelled for m in included)


def test_unknown_student_blocked_not_dropped():
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Nobody Known, Subject: Math", 13)
    msgs = build_messages([ev], roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert g.blocked
    assert "Nobody Known" in g.block_reasons[0]


def test_multi_student_one_group():
    ev = make_event("[TUT] Type: In-Person (Room #2), Teacher Name: Jeongbeen teacher, Student Name: MinYeong / Buhyeon, Subject: AP Bio", 15)
    msgs = build_messages([ev], roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert not g.blocked
    # 2 student phones + shared parent phone deduped -> 3 recipients
    assert sorted(g.phones) == ["404-555-0301", "404-555-0302", "404-555-0303"]
    assert g.group_mode
    assert g.identity == "MinYeong + Buhyeon"


def test_parent_only_single_number_degrades_to_1to1():
    ev = make_event("[TUT] Type: In-Person, Teacher Name: Jeongbeen teacher, Student Name: Jian Choi, Subject: Math", 15)
    msgs = build_messages([ev], roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert not g.blocked
    assert g.phones == ["404-555-0205"]
    assert not g.group_mode


def test_korean_note_stripped_for_parents_kept_for_teacher():
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math (Geometry 부분을 우선적으로)", 19)
    r = build_roster(TEACHERS, STUDENTS + [["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", ""]], [])
    msgs = build_messages([ev], r)
    t = next(m for m in msgs if m.kind == "teacher")
    g = next(m for m in msgs if m.kind == "student_group")
    assert "부분을" in t.body
    assert "부분을" not in g.body
    assert "ACT Math" in g.body


def test_same_student_two_sessions_merged_one_group():
    ev1 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Kyuheon (Andrew) Ahn, Subject: English", 13, "e1")
    ev2 = make_event("[TUT] Type: Online, Teacher Name: Jeongbeen teacher, Student Name: Kyuheon (Andrew) Ahn, Subject: Math", 17, "e2")
    msgs = build_messages([ev1, ev2], roster())
    groups = [m for m in msgs if m.kind == "student_group"]
    assert len(groups) == 1
    assert "2 sessions" in groups[0].body
