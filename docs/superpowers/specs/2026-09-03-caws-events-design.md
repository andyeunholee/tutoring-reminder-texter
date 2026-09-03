# [CAWS] events get reminder texts too

Date: 2026-09-03
Status: approved by owner

## Problem

The app only texts for `[TUT]` calendar events. The owner also runs
`[CAWS]` (college application) sessions whose titles use the exact same
field layout, e.g. real title:
`[CAWS] Type: ONLINE, Teacher name: Andy , Student Name: Yena, Subject: College Application (QB)`
(the field parser is already case-insensitive, so `Teacher name:` is fine).

## Behavior

- The tag filter accepts `[TUT]` or `[CAWS]` (case-insensitive, spaces ok).
  Everything downstream — parsing, roster matching, timezone shift, teacher
  full names, review-before-send — is byte-for-byte the same path.
- **Wording** (owner-provided template): texts describe the session by
  program. `[TUT]` → "tutoring", `[CAWS]` → "College Application":
  - student single: `... about Yena's College Application session.`
  - student multi, teacher single/multi: same substitution
    ("your Elite Prep College Application session/schedule").
  - a merged message covering BOTH programs on one day drops the qualifier:
    `... about Zena's sessions on ...` / `... your Elite Prep schedule ...`.
  - Date format (`September 3`) and `Link:` label stay as they are today,
    matching [TUT] texts; the owner's sample's `Sep 3` / `LINK:` were treated
    as hand-typed shorthand.
- `create_roster_sheet.bat`'s missing-name scan sees `[CAWS]` events too
  (it reuses the same tag regex), so new CAWS students get sheet rows added.
- Any other tag (`[XYZ]`) stays ignored.

## Touch points

- `src/tut_parser.py` — `TUT_TAG_RE` matches both tags and captures which;
  `ParsedTitle.program` = "TUT" | "CAWS".
- `src/templates.py` — the four templates take `{program_phrase}` ("tutoring "
  / "College Application " / "" when mixed).
- `src/message_builder.py` — `_PROGRAM_LABELS` map + `_program_phrase(events)`
  (single distinct label → "label ", mixed → "").
- `app.py` — the two "[TUT]" UI strings mention [CAWS] too.
- `README.md` — first paragraph mentions [CAWS].

## Out of scope

Different templates per program beyond the phrase, other tags, per-program
sheets or rosters.
