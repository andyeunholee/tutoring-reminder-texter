from src.canonical_names import CanonicalNames

# Column A of the Tutoring Daily Sheet's Students roster, as of Sept 2026.
NAMES = CanonicalNames((
    "Kyuheon (Andrew) Ahn", "MinYeong Heo", "BuHyeon Heo", "Daon Yu",
    "Suhyun Sean Byun", "Jian Choi", "Zena Kim", "Bill Yu", "Joanna Kim",
    "Sumin Yoon", "Andy Lee", "Mugyeol Evan Kim",
))


def test_short_calendar_names_become_the_roster_spelling():
    assert NAMES.resolve("Daon") == "Daon Yu"
    assert NAMES.resolve("Suhyun Byun") == "Suhyun Sean Byun"
    assert NAMES.resolve("minyeong") == "MinYeong Heo"
    assert NAMES.resolve("Sean") == "Suhyun Sean Byun"      # middle name alone
    assert NAMES.resolve("Mugyeol") == "Mugyeol Evan Kim"


def test_exact_and_full_names_pass_through_unchanged():
    assert NAMES.resolve("Kyuheon (Andrew) Ahn") == "Kyuheon (Andrew) Ahn"
    assert NAMES.resolve("zena kim") == "Zena Kim"          # case restored from roster


def test_ambiguous_or_unknown_names_are_left_alone():
    assert NAMES.resolve("Kim") == "Kim"                    # three Kims: do not guess
    assert NAMES.resolve("Yu") == "Yu"
    assert NAMES.resolve("Anthony") == "Anthony"            # not on the roster
    assert NAMES.resolve("") == ""
    assert CanonicalNames().resolve("Daon") == "Daon"       # no sheet configured


def test_resolve_all_keeps_order():
    assert NAMES.resolve_all(["Daon", "Bill", "Kim"]) == ["Daon Yu", "Bill Yu", "Kim"]
