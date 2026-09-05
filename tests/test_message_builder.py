from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.message_builder import build_messages, message_key
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


CST_STUDENTS = STUDENTS + [
    ["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", "", "CST"],
]

FULL_NAME_TEACHERS = [
    ["Joseph", "Joseph", "404-555-0102", "TRUE", "", "Mr. Joseph O'Hailey"],
    ["Jeongbeen", "Jeongbeen", "404-555-0101", "TRUE", ""],
]


def zena_roster():
    return build_roster(TEACHERS, CST_STUDENTS, [])


def test_cst_student_time_shifted_and_labeled():
    # Calendar 5-7 PM EST must read 4:00 PM - 6:00 PM (CST) in Zena's text.
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 17)
    msgs = build_messages([ev], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Time: 4:00 PM - 6:00 PM (CST)" in g.body


def test_cst_teacher_text_stays_est():
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 17)
    msgs = build_messages([ev], zena_roster())
    t = next(m for m in msgs if m.kind == "teacher")
    assert "5:00 PM - 7:00 PM" in t.body
    assert "(CST)" not in t.body


def test_cst_multi_session_lines_shifted():
    ev1 = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 13, "e1")
    ev2 = make_event("[TUT] Type: Online, Teacher Name: Jeongbeen teacher, Student Name: Zena Kim, Subject: English", 17, "e2")
    msgs = build_messages([ev1, ev2], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "- 12:00 PM - 2:00 PM (CST)" in g.body
    assert "- 4:00 PM - 6:00 PM (CST)" in g.body


def test_cst_shift_moves_the_date_too():
    # Midnight EST session belongs to the previous day in CST.
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 0)
    msgs = build_messages([ev], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Friday, July 31" in g.body


def test_est_student_body_unchanged():
    ev = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15)
    msgs = build_messages([ev], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Time: 3:00 PM - 5:00 PM" in g.body
    assert "(" not in g.body.split("Time:")[1].splitlines()[0]


def test_caws_texts_say_college_application():
    ev = make_event("[CAWS] Type: ONLINE, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: College Application", 15)
    msgs = build_messages([ev], roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Jian Choi's College Application session" in g.body
    t = next(m for m in msgs if m.kind == "teacher")
    assert "your Elite Prep College Application session" in t.body


def test_tut_texts_still_say_tutoring():
    ev = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15)
    msgs = build_messages([ev], roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Jian Choi's tutoring session" in g.body


def test_mixed_tut_caws_day_drops_the_qualifier():
    ev1 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 13, "e1")
    ev2 = make_event("[CAWS] Type: ONLINE, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: College Application", 15, "e2")
    msgs = build_messages([ev1, ev2], roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Jian Choi's sessions on" in g.body
    t = next(m for m in msgs if m.kind == "teacher")
    assert "your Elite Prep schedule for" in t.body


def test_student_text_uses_teacher_full_name():
    ev = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15)
    msgs = build_messages([ev], build_roster(FULL_NAME_TEACHERS, STUDENTS, []))
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Teacher: Mr. Joseph O'Hailey" in g.body
    t = next(m for m in msgs if m.kind == "teacher")
    assert "Hi Joseph," in t.body        # the teacher's own greeting is untouched


def test_student_multi_session_uses_teacher_full_name():
    ev1 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 13, "e1")
    ev2 = make_event("[TUT] Type: In-Person, Teacher Name: Jeongbeen teacher, Student Name: Jian Choi, Subject: Bio", 15, "e2")
    msgs = build_messages([ev1, ev2], build_roster(FULL_NAME_TEACHERS, STUDENTS, []))
    g = next(m for m in msgs if m.kind == "student_group")
    assert "with Mr. Joseph O'Hailey" in g.body
    assert "with Jeongbeen" in g.body    # blank Full Name falls back to the calendar name


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


def make_event_on(day, summary, hour, eid="e1"):
    """Same as make_event but on an explicit date, for multi-day tests."""
    return TutEvent(
        event_id=eid,
        recurring_event_id=None,
        raw_summary=summary,
        start=datetime(day.year, day.month, day.day, hour, 0, tzinfo=TZ),
        end=datetime(day.year, day.month, day.day, hour + 2, 0, tzinfo=TZ),
        html_link="",
        meet_link=None,
        parsed=parse_tut_title(summary),
    )


JOSEPH_ANDREW = ("[TUT] Type: In-Person, Teacher Name: Joseph teacher, "
                 "Student Name: Kyuheon (Andrew) Ahn, Subject: English")


def test_empty_day_tag_keeps_the_existing_keys():
    # app.py indexes widgets by these digests; changing them silently would
    # orphan every in-flight draft.
    assert message_key("teacher", "joseph", ["404-555-0102"]) == "49ed62fa90"
    assert message_key("teacher", "joseph", ["404-555-0102"], "") == "49ed62fa90"
    assert message_key(
        "student_group", "andrew", ["404-555-0202", "404-555-0203"]
    ) == "42dac460e9"


def test_day_tag_changes_the_key():
    a = message_key("teacher", "joseph", ["404-555-0102"], "2026-08-02")
    b = message_key("teacher", "joseph", ["404-555-0102"], "2026-08-03")
    assert a != b
    assert a != message_key("teacher", "joseph", ["404-555-0102"])


def test_same_person_on_two_days_gets_two_independent_messages():
    sun = build_messages([make_event_on(date(2026, 8, 2), JOSEPH_ANDREW, 13, "e1")],
                         roster(), day_tag="2026-08-02")
    mon = build_messages([make_event_on(date(2026, 8, 3), JOSEPH_ANDREW, 13, "e2")],
                         roster(), day_tag="2026-08-03")
    assert {m.key for m in sun}.isdisjoint({m.key for m in mon})


def test_per_day_building_keeps_each_date_line_correct():
    sun = build_messages([make_event_on(date(2026, 8, 2), JOSEPH_ANDREW, 13, "e1")],
                         roster(), day_tag="2026-08-02")
    mon = build_messages([make_event_on(date(2026, 8, 3), JOSEPH_ANDREW, 15, "e2")],
                         roster(), day_tag="2026-08-03")
    t_sun = next(m for m in sun if m.kind == "teacher")
    t_mon = next(m for m in mon if m.kind == "teacher")
    assert "Sunday, August 2" in t_sun.body
    assert "Monday, August 3" in t_mon.body
    # neither message mentions the other day
    assert "August 3" not in t_sun.body
    assert "August 2" not in t_mon.body
