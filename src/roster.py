"""Google Sheets roster: load, normalize names, match calendar names to rows."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

from googleapiclient.discovery import build

from src.tut_parser import MARKER_RE, PARENS_RE, TEACHER_SUFFIX_RE

_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


def norm_key(name: str, *, is_teacher: bool = False) -> str:
    s = unicodedata.normalize("NFKC", name or "")
    s = MARKER_RE.sub("", s.strip())
    if is_teacher:
        s = TEACHER_SUFFIX_RE.sub("", s)
    s = PARENS_RE.sub("", s)
    s = _NON_WORD_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).casefold().strip()


@dataclass(frozen=True)
class TeacherRow:
    calendar_name: str
    display_name: str
    phone: str
    active: bool
    notes: str = ""


@dataclass(frozen=True)
class StudentRow:
    calendar_name: str
    display_name: str
    student_phone: str
    parent_name: str
    parent_phone: str
    active: bool
    notes: str = ""


@dataclass(frozen=True)
class MatchResult:
    status: str  # exact | alias | fuzzy_subset | fuzzy_ratio | ambiguous | not_found | inactive
    row: TeacherRow | StudentRow | None = None
    method: str = ""
    candidates: list[str] = field(default_factory=list)
    norm_key: str = ""

    @property
    def matched(self) -> bool:
        return self.row is not None and self.status not in ("ambiguous", "not_found", "inactive")

    @property
    def is_fuzzy(self) -> bool:
        return self.status in ("fuzzy_subset", "fuzzy_ratio")


def _truthy(v: str) -> bool:
    return str(v).strip().lower() not in ("false", "no", "0", "n", "x")


@dataclass
class Roster:
    teachers: dict[str, TeacherRow] = field(default_factory=dict)
    students: dict[str, StudentRow] = field(default_factory=dict)
    aliases: dict[str, tuple[str, str]] = field(default_factory=dict)
    load_errors: list[str] = field(default_factory=list)

    def match_teacher(self, raw_name: str) -> MatchResult:
        return self._match(raw_name, self.teachers, "teacher", is_teacher=True)

    def match_student(self, raw_name: str) -> MatchResult:
        return self._match(raw_name, self.students, "student", is_teacher=False)

    def _match(self, raw_name: str, table: dict, kind: str, *, is_teacher: bool) -> MatchResult:
        key = norm_key(raw_name, is_teacher=is_teacher)
        if not key:
            return MatchResult(status="not_found", norm_key=key)

        # 1. exact
        if key in table:
            row = table[key]
            if not row.active:
                return MatchResult(status="inactive", row=row, method="exact", norm_key=key)
            return MatchResult(status="exact", row=row, method="exact", norm_key=key)

        # 2. alias
        alias = self.aliases.get(key)
        if alias and alias[0] == kind:
            canon = alias[1]
            if canon in table:
                row = table[canon]
                if not row.active:
                    return MatchResult(status="inactive", row=row, method="alias", norm_key=key)
                return MatchResult(status="alias", row=row, method="alias", norm_key=key)

        active_items = [(k, r) for k, r in table.items() if r.active]

        # 3. unique token-subset (either direction)
        tokens = set(key.split())
        subset_hits = [
            (k, r) for k, r in active_items
            if tokens <= set(k.split()) or set(k.split()) <= tokens
        ]
        if len(subset_hits) == 1:
            k, row = subset_hits[0]
            return MatchResult(status="fuzzy_subset", row=row, method="fuzzy_subset",
                               candidates=[row.calendar_name], norm_key=key)
        if len(subset_hits) > 1:
            return MatchResult(status="ambiguous", method="fuzzy_subset",
                               candidates=[r.calendar_name for _, r in subset_hits], norm_key=key)

        # 4. difflib ratio >= 0.90, unique
        ratio_hits = [
            (k, r) for k, r in active_items
            if difflib.SequenceMatcher(None, key, k).ratio() >= 0.90
        ]
        if len(ratio_hits) == 1:
            k, row = ratio_hits[0]
            return MatchResult(status="fuzzy_ratio", row=row, method="fuzzy_ratio",
                               candidates=[row.calendar_name], norm_key=key)
        if len(ratio_hits) > 1:
            return MatchResult(status="ambiguous", method="fuzzy_ratio",
                               candidates=[r.calendar_name for _, r in ratio_hits], norm_key=key)

        return MatchResult(status="not_found", norm_key=key)


def _get(row: list, i: int) -> str:
    return str(row[i]).strip() if i < len(row) else ""


def build_roster(teacher_rows: list[list], student_rows: list[list],
                 alias_rows: list[list]) -> Roster:
    """Pure constructor from raw sheet value rows (testable without API)."""
    roster = Roster()
    for row in teacher_rows:
        name = _get(row, 0)
        if not name:
            continue
        t = TeacherRow(
            calendar_name=name,
            display_name=_get(row, 1) or name,
            phone=_get(row, 2),
            active=_truthy(_get(row, 3) or "true"),
            notes=_get(row, 4),
        )
        key = norm_key(name, is_teacher=True)
        if key in roster.teachers:
            roster.load_errors.append(f"Duplicate teacher name in sheet: {name}")
        roster.teachers[key] = t

    for row in student_rows:
        name = _get(row, 0)
        if not name:
            continue
        s = StudentRow(
            calendar_name=name,
            display_name=_get(row, 1) or PARENS_RE.sub("", name).strip(),
            student_phone=_get(row, 2),
            parent_name=_get(row, 3),
            parent_phone=_get(row, 4),
            active=_truthy(_get(row, 5) or "true"),
            notes=_get(row, 6),
        )
        key = norm_key(name)
        if key in roster.students:
            roster.load_errors.append(f"Duplicate student name in sheet: {name}")
        roster.students[key] = s

    for row in alias_rows:
        written = _get(row, 0)
        kind = _get(row, 1).lower()
        canon = _get(row, 2)
        if not written or kind not in ("teacher", "student") or not canon:
            continue
        roster.aliases[norm_key(written, is_teacher=(kind == "teacher"))] = (
            kind,
            norm_key(canon, is_teacher=(kind == "teacher")),
        )
    return roster


def load_roster(credentials, spreadsheet_id: str, ranges: dict[str, str]) -> Roster:
    service = build("sheets", "v4", credentials=credentials)
    resp = (
        service.spreadsheets()
        .values()
        .batchGet(spreadsheetId=spreadsheet_id,
                  ranges=[ranges["teachers"], ranges["students"], ranges["aliases"]])
        .execute()
    )
    value_ranges = resp.get("valueRanges", [])
    def vals(i):
        return value_ranges[i].get("values", []) if i < len(value_ranges) else []
    return build_roster(vals(0), vals(1), vals(2))
