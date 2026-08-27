from src.roster import build_roster, norm_key

TEACHERS = [
    ["Jeongbeen", "Jeongbeen", "404-555-0101", "TRUE", ""],
    ["Joseph", "Joseph", "404-555-0102", "TRUE", ""],
    ["Peter", "Peter", "", "TRUE", "no phone yet"],
    ["OldGuy", "OldGuy", "404-555-0199", "FALSE", "left"],
]
STUDENTS = [
    ["Kyuheon (Andrew) Ahn", "Andrew", "404-555-0202", "Mrs. Ahn", "404-555-0203", "TRUE", ""],
    ["Jian Choi", "", "404-555-0204", "", "404-555-0205", "TRUE", ""],
    ["Daon Kim", "Daon", "", "Mrs. Kim", "404-555-0206", "TRUE", ""],
    ["Daon Park", "Daon P", "", "Mr. Park", "404-555-0207", "TRUE", ""],
    ["Zena Kim", "Zena", "404-555-0208", "", "", "TRUE", ""],
]
ALIASES = [
    ["MinYeong", "student", "Zena Kim"],
]


def make_roster():
    return build_roster(TEACHERS, STUDENTS, ALIASES)


def test_norm_key():
    assert norm_key(" v Jeongbeen teacher", is_teacher=True) == "jeongbeen"
    assert norm_key("Kyuheon (Andrew) Ahn") == "kyuheon ahn"
    assert norm_key("  v Jian Choi ") == "jian choi"
    assert norm_key("? Peter teacher", is_teacher=True) == "peter"


def test_exact_teacher_with_markers():
    r = make_roster()
    m = r.match_teacher(" v Jeongbeen teacher")
    assert m.status == "exact"
    assert m.row.phone == "404-555-0101"


def test_exact_student_nickname():
    r = make_roster()
    m = r.match_student("Kyuheon (Andrew) Ahn")
    assert m.status == "exact"
    assert m.row.display_name == "Andrew"


def test_alias():
    r = make_roster()
    m = r.match_student("MinYeong")
    assert m.status == "alias"
    assert m.row.calendar_name == "Zena Kim"


def test_fuzzy_subset_unique():
    r = make_roster()
    m = r.match_student("Jian")
    assert m.status == "fuzzy_subset"
    assert m.row.calendar_name == "Jian Choi"


def test_ambiguous():
    r = make_roster()
    m = r.match_student("Daon")
    assert m.status == "ambiguous"
    assert sorted(m.candidates) == ["Daon Kim", "Daon Park"]


def test_not_found():
    r = make_roster()
    m = r.match_student("Totally Unknown")
    assert m.status == "not_found"
    assert not m.matched


def test_inactive():
    r = make_roster()
    m = r.match_teacher("OldGuy")
    assert m.status == "inactive"
    assert not m.matched


def test_display_name_fallback_strips_parens():
    r = make_roster()
    m = r.match_student("Jian Choi")
    assert m.row.display_name == "Jian Choi"


def test_student_timezone_column():
    rows = [["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", "", "cst"]]
    r = build_roster(TEACHERS, rows, [])
    assert r.match_student("Zena Kim").row.timezone == "CST"
    assert r.load_errors == []


def test_student_timezone_missing_column_is_est():
    r = make_roster()
    assert r.match_student("Jian Choi").row.timezone == ""


def test_student_timezone_typo_is_flagged_not_silent():
    rows = [["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", "", "CTS"]]
    r = build_roster(TEACHERS, rows, [])
    assert r.match_student("Zena Kim").row.timezone == ""
    assert any("CTS" in e and "Zena Kim" in e for e in r.load_errors)


def test_teacher_full_name_column():
    rows = [["Joseph", "Joseph", "404-555-0102", "TRUE", "", "Mr. Joseph O'Hailey"]]
    r = build_roster(rows, STUDENTS, [])
    assert r.match_teacher("Joseph teacher").row.full_name == "Mr. Joseph O'Hailey"
