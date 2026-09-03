"""Parser tests against 11 verbatim titles from the live calendar."""

import pytest

from src.tut_parser import parse_tut_title, split_students, extract_meet_link

T1 = " [TUT] Type: In-Person (Room #1), Teacher Name: Joseph teacher, Student Name: Kyuheon (Andrew) Ahn, Subject:  English "
T2 = "[TUT] Type: In-Person, Teacher Name:  v Jeongbeen teacher, Student Name:   v Jian Choi , Subject: Geometry & Alg II (선행) & Bio (학교 공부)"
T3 = "[TUT] Type: Online, Teacher Name:  Peter teacher, Student Name: Zena Kim, Subject: ACT Math (Geometry 부분을 우선적으로)"
T4 = "[TUT] Type: In-Person, Teacher Name:   Jeongbeen teacher, Student Name: Suhyun Byun, Subject: Alg I(9th) &  Geometry & Alg II (선행) & Bio (학교 공부)"
T5 = "canceled by student: [TUT] Type: In-Person, Teacher Name:  John teacher, Student Name: Joanna Kim, Subject: 9th Eng"
T6 = "canceled b/c summer : [TUT] Type: In-Person (Room #2), Teacher Name: Joseph teacher, Student Name: Daon, Subject:  English"
T7 = "canceled by student : [TUT] Type: In-Person (Room #2), Teacher Name:  Jeongbeen teacher, Student Name: MinYeong / Buhyeon, Subject: AP Bio & Chem H & AP  Precal "
T8 = "(canceled by student )[TUT] Type: In-Person (Room #2), Teacher Name:  Jeongbeen teacher, Student Name: MinYeong / Buhyeon, Subject: AP Bio & Chem H & AP  Precal "
T9 = "canceled by student: [TUT] Type: In-Person (Room #2), Teacher Name:? Peter teacher, Student Name: v Daon, Subject:  Math (SAT 교재시도해볼것)"
T10 = "[TUT] Type: In-Person (Room #2), Teacher Name:? Peter teacher, Student Name: v Daon, Subject:  Math (SAT 교재시도해볼것)"
T11 = "[TUT] Type: Online, Teacher Name:  Joseph teacher, Student Name:  Daon, Subject:  SAT English"


def test_basic_fields_with_nickname():
    p = parse_tut_title(T1)
    assert p.has_tut_tag
    assert not p.is_cancelled
    assert p.teacher_name == "Joseph"
    assert p.student_names == ["Kyuheon (Andrew) Ahn"]
    assert p.subject == "English"
    assert p.session_type == "In-Person (Room #1)"
    assert p.room == "Room #1"
    assert not p.is_online


def test_v_markers_stripped_both_names():
    p = parse_tut_title(T2)
    assert p.teacher_name == "Jeongbeen"
    assert p.student_names == ["Jian Choi"]
    assert p.subject == "Geometry & Alg II (선행) & Bio (학교 공부)"
    assert p.subject_clean == "Geometry & Alg II & Bio"


def test_online_with_korean_subject():
    p = parse_tut_title(T3)
    assert p.is_online
    assert p.teacher_name == "Peter"
    assert p.student_names == ["Zena Kim"]
    assert p.subject_clean == "ACT Math"


def test_ampersands_and_parens_in_subject():
    p = parse_tut_title(T4)
    assert p.teacher_name == "Jeongbeen"
    assert p.student_names == ["Suhyun Byun"]
    assert p.subject == "Alg I(9th) & Geometry & Alg II (선행) & Bio (학교 공부)"
    assert p.subject_clean == "Alg I & Geometry & Alg II & Bio"


@pytest.mark.parametrize("title", [T5, T6, T7, T8, T9])
def test_cancel_prefixes_detected(title):
    p = parse_tut_title(title)
    assert p.is_cancelled
    assert p.has_tut_tag


def test_cancel_marker_text():
    p = parse_tut_title(T6)
    assert "canceled" in p.cancel_marker.lower()
    assert p.teacher_name == "Joseph"
    assert p.student_names == ["Daon"]


def test_multi_student_slash():
    p = parse_tut_title(T7)
    assert p.student_names == ["MinYeong", "Buhyeon"]
    assert p.subject == "AP Bio & Chem H & AP Precal"


def test_question_mark_marker():
    p = parse_tut_title(T10)
    assert not p.is_cancelled
    assert p.teacher_name == "Peter"
    assert p.student_names == ["Daon"]
    assert p.room == "Room #2"
    assert p.subject_clean == "Math"


def test_online_no_room():
    p = parse_tut_title(T11)
    assert p.is_online
    assert p.room is None
    assert p.teacher_name == "Joseph"
    assert p.student_names == ["Daon"]
    assert p.subject == "SAT English"


def test_non_tut_title():
    p = parse_tut_title("Meeting with parents")
    assert not p.has_tut_tag


def test_caws_tag_is_parsed():
    p = parse_tut_title("[CAWS] Type: ONLINE, Teacher Name: Andy teacher, Student Name: Zena, Subject:  College Application")
    assert p.has_tut_tag
    assert p.program == "CAWS"
    assert p.teacher_name == "Andy"
    assert p.student_names == ["Zena"]


def test_caws_lowercase_field_and_no_teacher_suffix():
    # Real title from the calendar: lowercase "Teacher name:", no "teacher" suffix.
    p = parse_tut_title("[CAWS] Type: ONLINE, Teacher name: Andy , Student Name: Yena, Subject: College Application (QB)")
    assert p.has_tut_tag
    assert p.teacher_name == "Andy"
    assert p.student_names == ["Yena"]
    assert p.subject_clean == "College Application"


def test_tut_events_report_their_program():
    assert parse_tut_title(T1).program == "TUT"


def test_missing_fields_warn():
    p = parse_tut_title("[TUT] Type: Online, Subject: Math")
    assert p.has_tut_tag
    assert p.teacher_name == ""
    assert p.student_names == []
    assert p.warnings


def test_initial_with_period_is_safe():
    p = parse_tut_title("[TUT] Type: Online, Teacher Name: V. Kim teacher, Student Name: J. Lee, Subject: Math")
    assert p.teacher_name == "V. Kim"
    assert p.student_names == ["J. Lee"]


def test_split_students_variants():
    assert split_students("MinYeong / Buhyeon") == ["MinYeong", "Buhyeon"]
    assert split_students("A & B") == ["A", "B"]
    assert split_students("Zena Kim") == ["Zena Kim"]


def test_extract_meet_link():
    desc = 'LINK: <a href="https://meet.google.com/oba-mwvn-jei">https://meet.google.com/oba-mwvn-jei</a>'
    assert extract_meet_link(desc) == "https://meet.google.com/oba-mwvn-jei"
    assert extract_meet_link(None) is None
    assert extract_meet_link("no link here") is None
