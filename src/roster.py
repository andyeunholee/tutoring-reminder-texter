"""Google Sheets roster: load, normalize names, match calendar names to rows."""

from __future__ import annotations

import difflib
import re
import time
import unicodedata
from dataclasses import dataclass, field

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.tut_parser import MARKER_RE, PARENS_RE, TEACHER_SUFFIX_RE

_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)
# Separators between two numbers sharing one cell. A single space is NOT one of
# them: it lives inside "(678) 780-5797".
_PHONE_SPLIT_RE = re.compile(r"[,;/\n]+| {2,}")

# Students-tab Time Zone values the app understands. Blank and EST mean
# "leave times alone"; the rest shift the displayed clock in message_builder.
_KNOWN_TIMEZONES = ("", "EST", "CST", "MST", "PST")


def split_phones(raw) -> list[str]:
    """The numbers held in one sheet cell.

    Families often want both parents on the reminder, and the sheet keeps a
    single Parent Phone column. Splitting has to happen here: handing the raw
    cell to normalize_phone_number would strip the punctuation out of
    "(678) 780-5797, (404) 123-4567" and leave one 20-digit string that reaches
    nobody at all.
    """
    # Numbers copied out of Google Voice carry invisible bidi marks (U+202A/
    # U+202C). They reach nobody's eye but they do reach the recipient dedupe,
    # which compares raw strings — so the same number pasted with and without
    # them would text one parent twice.
    cleaned = "".join(ch for ch in str(raw or "")
                      if unicodedata.category(ch) != "Cf")
    return [p for p in (x.strip() for x in _PHONE_SPLIT_RE.split(cleaned)) if p]


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
    full_name: str = ""   # exact text for student texts, e.g. "Mr. Joseph O'Hailey"


@dataclass(frozen=True)
class StudentRow:
    calendar_name: str
    display_name: str
    student_phone: str
    parent_name: str
    parent_phones: tuple[str, ...]   # one cell can list several
    active: bool
    notes: str = ""
    timezone: str = ""               # "", "EST", "CST", "MST", "PST"


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
            full_name=_get(row, 5),
        )
        key = norm_key(name, is_teacher=True)
        if key in roster.teachers:
            roster.load_errors.append(f"Duplicate teacher name in sheet: {name}")
        roster.teachers[key] = t

    for row in student_rows:
        name = _get(row, 0)
        if not name:
            continue
        raw_tz = _get(row, 7)
        tz = raw_tz.strip().upper()
        if tz not in _KNOWN_TIMEZONES:
            # Never fall back silently: a typo here would put a wrong clock
            # time in front of a parent.
            roster.load_errors.append(
                f'Student "{name}" has an unrecognized Time Zone "{raw_tz}" '
                "(use CST, MST, or PST; blank = EST). Times left in EST."
            )
            tz = ""
        s = StudentRow(
            calendar_name=name,
            display_name=_get(row, 1) or PARENS_RE.sub("", name).strip(),
            student_phone=_get(row, 2),
            parent_name=_get(row, 3),
            parent_phones=tuple(split_phones(_get(row, 4))),
            active=_truthy(_get(row, 5) or "true"),
            notes=_get(row, 6),
            timezone=tz,
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


class RosterUnavailable(RuntimeError):
    """Google Sheets could not be read right now (outage, quota, network)."""


def load_roster(credentials, spreadsheet_id: str, ranges: dict[str, str],
                *, attempts: int = 4) -> Roster:
    """Read the roster, retrying transient Google failures with backoff.

    Sheets occasionally returns 503/500 on the values endpoint while the rest
    of the API is healthy. Retrying rides out the short ones; a persistent
    failure is surfaced as RosterUnavailable so the UI can say what is wrong
    instead of dumping a stack trace.
    """
    service = build("sheets", "v4", credentials=credentials)
    delay, last = 2.0, None
    for attempt in range(1, attempts + 1):
        try:
            resp = (
                service.spreadsheets()
                .values()
                .batchGet(spreadsheetId=spreadsheet_id,
                          ranges=[ranges["teachers"], ranges["students"],
                                  ranges["aliases"]])
                .execute()
            )
            break
        except HttpError as e:
            last = e
            if e.resp.status not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise RosterUnavailable(_roster_error_text(e)) from e
            time.sleep(delay)
            delay *= 2
    else:  # pragma: no cover - loop always breaks or raises
        raise RosterUnavailable(_roster_error_text(last))

    value_ranges = resp.get("valueRanges", [])
    def vals(i):
        return value_ranges[i].get("values", []) if i < len(value_ranges) else []
    return build_roster(vals(0), vals(1), vals(2))


def _roster_error_text(err) -> str:
    status = getattr(getattr(err, "resp", None), "status", None)
    if status in (500, 502, 503, 504):
        return ("Google Sheets is temporarily unavailable (error "
                f"{status}). This is an outage on Google's side, not a problem "
                "with your roster. Wait a few minutes and search again.")
    if status == 429:
        return ("Google Sheets rate limit reached. Wait a minute and search "
                "again.")
    if status == 403:
        return ("No permission to read the roster sheet. Check that the "
                "signed-in Google account can open it.")
    if status == 404:
        return ("Roster sheet not found. Check ROSTER_SPREADSHEET_ID in .env.")
    return f"Could not read the roster sheet: {err}"
