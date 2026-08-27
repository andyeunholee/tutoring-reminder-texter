# Per-student timezone display in reminder texts

Date: 2026-08-27
Status: approved by owner

## Problem

All session times in reminder texts are shown in EST (the calendar's zone).
Student Zena lives in Central Time; her family reads "5:00 PM" and shows up an
hour off. Her texts must show the time shifted one hour earlier with a "(CST)"
label: calendar `5:00 PM - 6:00 PM` (EST) → text `Time: 4:00 PM - 5:00 PM (CST)`.

## Decision: configuration lives in the roster sheet

A new **"Time Zone" column at the end of the Students tab**. Owner writes `CST`
in Zena's row. Blank = EST, unchanged behavior. Recognized values and their
offsets from EST: `CST` = -1h, `MST` = -2h, `PST` = -3h, `EST`/blank = no
change. Fixed offsets are safe year-round: the US zones observe daylight saving
together. Case-insensitive, whitespace tolerated.

Rejected alternatives: `.env` mapping (hidden from the sheet where the rest of
the student data lives), hardcoding Zena (breaks on the next remote student).

## Behavior

- **Student+parent texts only.** For a student whose row has a timezone, every
  time in their group text is shifted and suffixed: single-session
  `Time: 4:00 PM - 5:00 PM (CST)` and each `- 4:00 PM - 5:00 PM - ...` line in
  multi-session blocks. The date line uses the shifted start too (a shift
  across midnight moves the date with it).
- **Teacher texts never change** — teachers are local (EST).
- **Sibling groups** (one text per household) use the first non-empty timezone
  among the group's student rows; same household, same zone.
- **Typo defense:** an unrecognized value (e.g. `CTS`) must NOT silently fall
  back to EST — a wrong time reaching a parent is the worst failure. It is
  reported through the existing roster load-error list that app.py already
  shows, and the student's text is built as EST with no suffix.

## Touch points

- `src/roster.py` — `StudentRow.timezone` (new field, default `""`), parsed
  from column index 7; validation warning into `roster.load_errors`.
- `src/message_builder.py` — `_fmt_date_long`/`_time_range` gain a shift;
  student-body renderers look up the group's timezone and pass it down.
  `message_key` is untouched (identity does not depend on display times).
- `scripts/create_roster_sheet.py` — add the "Time Zone" header for new sheets.
  Existing sheets need no migration: a missing column reads as blank.
- `README.md` — one bullet in the roster-sheet section.
- Tests: row parsing incl. bad value warning, shift math, student single and
  multi bodies, sibling group, teacher body unchanged.

## Out of scope

Non-US zones, minute-offset zones, per-teacher zones, showing "(EST)" for
local students.
