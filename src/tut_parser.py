"""Pure parsing of [TUT] calendar event titles. No I/O here."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

# [TUT] tutoring and [CAWS] college-application sessions share one title
# format and one texting pipeline; only the wording of the texts differs.
TUT_TAG_RE = re.compile(r"\[\s*(TUT|CAWS)\s*\]", re.IGNORECASE)
CANCEL_RE = re.compile(r"(cancell?ed|cancel\b|취소|no[\s-]*show|reschedul)", re.IGNORECASE)
FIELD_RE = re.compile(
    r"(?P<label>Type|Teacher\s*Name|Student\s*Name|Subject)\s*:\s*"
    r"(?P<value>.*?)"
    r"(?=\s*,?\s*(?:Type|Teacher\s*Name|Student\s*Name|Subject)\s*:|$)",
    re.IGNORECASE | re.DOTALL,
)
# Junk markers: single chars followed by whitespace, repeated ("v ", "? ", "x ").
# "V. Kim" / "Victor" are safe because the char must be immediately followed by space.
MARKER_RE = re.compile(r"^(?:[vVxX?*✓√\-]\s+)+")
TEACHER_SUFFIX_RE = re.compile(r"\s*\bteachers?\b\s*$", re.IGNORECASE)
STUDENT_SPLIT_RE = re.compile(r"\s*(?:/|&|,|\band\b)\s*")
PARENS_RE = re.compile(r"\s*\([^)]*\)")
ROOM_RE = re.compile(r"(Room\s*#?\s*[\w-]+)", re.IGNORECASE)
MEET_LINK_RE = re.compile(r"https://meet\.google\.com/[a-z]{3,}-[a-z]{3,}-[a-z]{3,}", re.IGNORECASE)


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def strip_markers(s: str) -> str:
    return MARKER_RE.sub("", s)


def strip_teacher_suffix(s: str) -> str:
    return TEACHER_SUFFIX_RE.sub("", s)


def split_students(s: str) -> list[str]:
    return [p for p in (normalize_ws(x) for x in STUDENT_SPLIT_RE.split(s)) if p]


def strip_parentheticals(s: str) -> str:
    return normalize_ws(PARENS_RE.sub("", s))


def _clean_value(v: str) -> str:
    v = unicodedata.normalize("NFKC", v)
    v = v.strip().strip(",").strip()
    return normalize_ws(v)


def _clean_name(v: str) -> str:
    return normalize_ws(strip_markers(_clean_value(v)))


@dataclass(frozen=True)
class ParsedTitle:
    has_tut_tag: bool = False
    is_cancelled: bool = False
    cancel_marker: str = ""
    session_type: str = ""
    is_online: bool = False
    room: str | None = None
    teacher_raw: str = ""
    teacher_name: str = ""
    students_raw: str = ""
    student_names: list[str] = field(default_factory=list)
    subject: str = ""
    subject_clean: str = ""
    program: str = ""   # "TUT" | "CAWS" (empty when has_tut_tag is False)
    warnings: list[str] = field(default_factory=list)


def parse_tut_title(summary: str) -> ParsedTitle:
    summary = summary or ""
    tag_match = TUT_TAG_RE.search(summary)
    if not tag_match:
        return ParsedTitle(has_tut_tag=False)

    program = tag_match.group(1).upper()
    prefix = summary[: tag_match.start()]
    rest = summary[tag_match.end():]

    cancel_hit = CANCEL_RE.search(prefix) or CANCEL_RE.search(summary)
    is_cancelled = cancel_hit is not None
    cancel_marker = normalize_ws(prefix.strip(" ():-,")) if is_cancelled else ""
    if is_cancelled and not cancel_marker:
        cancel_marker = normalize_ws(cancel_hit.group(0))

    fields: dict[str, str] = {}
    for m in FIELD_RE.finditer(rest):
        label = re.sub(r"\s+", " ", m.group("label")).strip().lower()
        fields[label] = m.group("value")

    warnings: list[str] = []

    session_type = _clean_value(fields.get("type", ""))
    if not session_type:
        warnings.append("missing Type")
    is_online = "online" in session_type.lower()
    room_m = ROOM_RE.search(session_type)
    room = normalize_ws(room_m.group(1)) if room_m else None

    teacher_raw = fields.get("teacher name", "")
    teacher_name = strip_teacher_suffix(_clean_name(teacher_raw)).strip()
    if not teacher_name:
        warnings.append("missing Teacher Name")

    students_raw = fields.get("student name", "")
    student_names = split_students(_clean_name(students_raw))
    if not student_names:
        warnings.append("no students parsed")

    subject = _clean_value(fields.get("subject", ""))
    if not subject:
        warnings.append("missing Subject")
    subject_clean = strip_parentheticals(subject)

    return ParsedTitle(
        has_tut_tag=True,
        is_cancelled=is_cancelled,
        cancel_marker=cancel_marker,
        session_type=session_type,
        is_online=is_online,
        room=room,
        teacher_raw=teacher_raw,
        teacher_name=teacher_name,
        students_raw=students_raw,
        student_names=student_names,
        subject=subject,
        subject_clean=subject_clean,
        program=program,
        warnings=warnings,
    )


def extract_meet_link(description: str | None) -> str | None:
    if not description:
        return None
    m = MEET_LINK_RE.search(description)
    return m.group(0) if m else None


@dataclass(frozen=True)
class TutEvent:
    event_id: str
    recurring_event_id: str | None
    raw_summary: str
    start: datetime
    end: datetime
    html_link: str
    meet_link: str | None
    parsed: ParsedTitle

    @property
    def teacher_name(self) -> str:
        return self.parsed.teacher_name

    @property
    def student_names(self) -> list[str]:
        return self.parsed.student_names

    @property
    def subject(self) -> str:
        return self.parsed.subject

    @property
    def is_cancelled(self) -> bool:
        return self.parsed.is_cancelled


def build_tut_event(raw: dict, tz: ZoneInfo) -> TutEvent | None:
    """raw is a Calendar API event resource. Returns None for all-day/malformed."""
    start_s = (raw.get("start") or {}).get("dateTime")
    end_s = (raw.get("end") or {}).get("dateTime")
    if not start_s or not end_s:
        return None
    start = datetime.fromisoformat(start_s).astimezone(tz)
    end = datetime.fromisoformat(end_s).astimezone(tz)
    return TutEvent(
        event_id=raw.get("id", ""),
        recurring_event_id=raw.get("recurringEventId"),
        raw_summary=raw.get("summary", ""),
        start=start,
        end=end,
        html_link=raw.get("htmlLink", ""),
        meet_link=extract_meet_link(raw.get("description")),
        parsed=parse_tut_title(raw.get("summary", "")),
    )
