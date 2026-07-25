"""Turn TutEvents + Roster into reviewable OutboundMessages."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from src import templates
from src.roster import Roster
from src.tut_parser import TutEvent


@dataclass
class Recipient:
    label: str   # "Jeongbeen (teacher)", "Andrew (student)", "Mrs. Ahn (parent)"
    phone: str


@dataclass
class OutboundMessage:
    key: str
    kind: str                    # "teacher" | "student_group"
    identity: str                # display label for the row header
    recipients: list[Recipient]
    group_mode: bool
    body: str
    events: list[TutEvent]
    blocked: bool = False
    block_reasons: list[str] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    is_cancelled: bool = False

    @property
    def phones(self) -> list[str]:
        return [r.phone for r in self.recipients if r.phone]


def message_key(kind: str, identity: str, phones: list[str]) -> str:
    basis = f"{kind}|{identity.casefold()}|{','.join(sorted(phones))}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]


def _fmt_date_long(dt) -> str:
    return f"{dt:%A}, {dt:%B} {dt.day}"


def _fmt_time(dt) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _time_range(ev: TutEvent) -> str:
    return f"{_fmt_time(ev.start)} - {_fmt_time(ev.end)}"


def _location_line(ev: TutEvent) -> str:
    if ev.parsed.is_online:
        return "Format: Online"
    if ev.parsed.session_type:
        return f"Location: {ev.parsed.session_type}"
    return ""


def _meet_line(ev: TutEvent) -> str:
    if ev.parsed.is_online and ev.meet_link:
        return f"\nLink: {ev.meet_link}"
    return ""


def _tidy(body: str) -> str:
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def _teacher_sessions_block(events: list[TutEvent]) -> str:
    lines = []
    for ev in events:
        students = ", ".join(ev.student_names) or "(no student parsed)"
        line = f"- {_time_range(ev)} - {students} - {ev.subject} ({ev.parsed.session_type})"
        lines.append(line)
        if ev.parsed.is_online and ev.meet_link:
            lines.append(f"  Link: {ev.meet_link}")
    return "\n".join(lines)


def _student_sessions_block(events: list[TutEvent]) -> str:
    lines = []
    for ev in events:
        line = (
            f"- {_time_range(ev)} - {ev.parsed.subject_clean or ev.subject}"
            f" with {ev.teacher_name} ({ev.parsed.session_type})"
        )
        lines.append(line)
        if ev.parsed.is_online and ev.meet_link:
            lines.append(f"  Link: {ev.meet_link}")
    return "\n".join(lines)


def render_teacher_body(display_name: str, events: list[TutEvent], org_name: str) -> str:
    if len(events) == 1:
        ev = events[0]
        return _tidy(templates.TEACHER_SINGLE.format(
            recipient_name=display_name,
            org_name=org_name,
            date_long=_fmt_date_long(ev.start),
            time_range=_time_range(ev),
            student_names=", ".join(ev.student_names),
            subject=ev.subject,
            location_line=_location_line(ev),
            meet_line=_meet_line(ev),
        ))
    return _tidy(templates.TEACHER_MULTI.format(
        recipient_name=display_name,
        org_name=org_name,
        date_long=_fmt_date_long(events[0].start),
        session_count=len(events),
        sessions_block=_teacher_sessions_block(events),
    ))


def render_student_body(display_name: str, events: list[TutEvent], org_name: str) -> str:
    if len(events) == 1:
        ev = events[0]
        return _tidy(templates.STUDENT_GROUP_SINGLE.format(
            recipient_name=display_name,
            org_name=org_name,
            date_long=_fmt_date_long(ev.start),
            time_range=_time_range(ev),
            teacher_name=ev.teacher_name,
            subject=ev.parsed.subject_clean or ev.subject,
            location_line=_location_line(ev),
            meet_line=_meet_line(ev),
        ))
    return _tidy(templates.STUDENT_GROUP_MULTI.format(
        recipient_name=display_name,
        org_name=org_name,
        date_long=_fmt_date_long(events[0].start),
        session_count=len(events),
        sessions_block=_student_sessions_block(events),
    ))


def build_messages(
    events: list[TutEvent],
    roster: Roster,
    *,
    merge_sessions_per_recipient: bool = True,
    include_cancelled: bool = False,
    org_name: str = "Elite Prep",
) -> list[OutboundMessage]:
    active = [e for e in events if include_cancelled or not e.is_cancelled]
    active.sort(key=lambda e: e.start)

    messages: list[OutboundMessage] = []
    messages.extend(_build_teacher_messages(active, roster, merge_sessions_per_recipient, org_name))
    messages.extend(_build_student_messages(active, roster, merge_sessions_per_recipient, org_name))
    return messages


def _build_teacher_messages(events, roster, merge, org_name) -> list[OutboundMessage]:
    groups: dict[str, dict] = {}
    for ev in events:
        raw_name = ev.teacher_name
        if not raw_name:
            continue
        match = roster.match_teacher(raw_name)
        gkey = match.row.calendar_name if match.matched else f"?{raw_name}"
        if not merge:
            gkey = f"{gkey}|{ev.event_id}"
        g = groups.setdefault(gkey, {"match": match, "raw_name": raw_name, "events": []})
        g["events"].append(ev)

    out = []
    for g in groups.values():
        match, raw_name, evs = g["match"], g["raw_name"], g["events"]
        badges, reasons = [], []
        recipients: list[Recipient] = []
        display = raw_name

        if match.matched:
            display = match.row.display_name
            if match.row.phone:
                recipients.append(Recipient(f"{display} (teacher)", match.row.phone))
            else:
                reasons.append(f'Teacher "{match.row.calendar_name}" has no phone in the Teachers tab.')
            if match.is_fuzzy:
                badges.append(f'fuzzy match: "{raw_name}" -> "{match.row.calendar_name}"')
        elif match.status == "ambiguous":
            reasons.append(
                f'Teacher "{raw_name}" is ambiguous in the roster. Candidates: '
                + ", ".join(match.candidates)
                + ". Add an Aliases row to resolve."
            )
        elif match.status == "inactive":
            reasons.append(f'Teacher "{raw_name}" is marked inactive in the Teachers tab.')
        else:
            reasons.append(
                f'No Teachers row for "{raw_name}" (normalized: "{match.norm_key}"). '
                f"Add it to the Teachers tab or map it in Aliases."
            )

        body = render_teacher_body(display, evs, org_name)
        phones = [r.phone for r in recipients]
        out.append(OutboundMessage(
            key=message_key("teacher", match.norm_key or raw_name, phones),
            kind="teacher",
            identity=display,
            recipients=recipients,
            group_mode=len(phones) > 1,
            body=body,
            events=evs,
            blocked=bool(reasons),
            block_reasons=reasons,
            badges=badges,
            is_cancelled=all(e.is_cancelled for e in evs),
        ))
    return out


def _build_student_messages(events, roster, merge, org_name) -> list[OutboundMessage]:
    # One group message per event containing ALL that event's students + parents
    # (user's explicit choice). Events whose recipient phone set is identical
    # merge into one message when merge=True.
    prelim: list[dict] = []
    for ev in events:
        if not ev.student_names:
            continue
        recipients: list[Recipient] = []
        display_names: list[str] = []
        badges, reasons = [], []
        norm_ids = []
        for raw_name in ev.student_names:
            match = roster.match_student(raw_name)
            norm_ids.append(match.norm_key or raw_name)
            if match.matched:
                row = match.row
                display_names.append(row.display_name)
                if match.is_fuzzy:
                    badges.append(f'fuzzy match: "{raw_name}" -> "{row.calendar_name}"')
                if row.student_phone:
                    recipients.append(Recipient(f"{row.display_name} (student)", row.student_phone))
                if row.parent_phone:
                    plabel = row.parent_name or f"{row.display_name}'s parent"
                    recipients.append(Recipient(f"{plabel} (parent)", row.parent_phone))
                if not row.student_phone and not row.parent_phone:
                    reasons.append(
                        f'Student "{row.calendar_name}" has no student or parent phone in the Students tab.'
                    )
            elif match.status == "ambiguous":
                display_names.append(raw_name)
                reasons.append(
                    f'Student "{raw_name}" is ambiguous. Candidates: '
                    + ", ".join(match.candidates)
                    + ". Add an Aliases row to resolve."
                )
            elif match.status == "inactive":
                display_names.append(raw_name)
                reasons.append(f'Student "{raw_name}" is marked inactive in the Students tab.')
            else:
                display_names.append(raw_name)
                reasons.append(
                    f'No Students row for "{raw_name}" (normalized: "{match.norm_key}"). '
                    f"Add it to the Students tab or map it in Aliases."
                )
        prelim.append({
            "event": ev,
            "recipients": recipients,
            "display": " + ".join(display_names),
            "identity_norm": "+".join(sorted(norm_ids)),
            "badges": badges,
            "reasons": reasons,
        })

    # merge by identical recipient phone sets (only unblocked entries can merge safely)
    groups: dict[str, dict] = {}
    for p in prelim:
        phone_set = ",".join(sorted({r.phone for r in p["recipients"]}))
        gkey = f"{p['identity_norm']}|{phone_set}" if merge else f"{p['identity_norm']}|{p['event'].event_id}"
        g = groups.setdefault(gkey, {**p, "events": []})
        g["events"].append(p["event"])
        for b in p["badges"]:
            if b not in g["badges"]:
                g["badges"].append(b)
        for r in p["reasons"]:
            if r not in g["reasons"]:
                g["reasons"].append(r)

    out = []
    for g in groups.values():
        evs = sorted(g["events"], key=lambda e: e.start)
        # dedupe recipients by phone
        seen, recipients = set(), []
        for r in g["recipients"]:
            if r.phone not in seen:
                seen.add(r.phone)
                recipients.append(r)
        body = render_student_body(g["display"], evs, org_name)
        phones = [r.phone for r in recipients]
        badges = list(g["badges"])
        if len(evs) > 1:
            badges.append(f"{len(evs)} sessions merged into one message")
        out.append(OutboundMessage(
            key=message_key("student_group", g["identity_norm"], phones),
            kind="student_group",
            identity=g["display"],
            recipients=recipients,
            group_mode=len(phones) > 1,
            body=body,
            events=evs,
            blocked=bool(g["reasons"]),
            block_reasons=list(g["reasons"]),
            badges=badges,
            is_cancelled=all(e.is_cancelled for e in evs),
        ))
    return out
