# Teacher texts name students by the roster's column A

Date: 2026-09-05
Status: approved by owner

## Problem

The teacher reminder's `Student:` line repeats the calendar's short form
("Suhyun Byun"). The owner wants it to read exactly like column A of the
roster's Students tab ("Suhyun Sean Byun").

An earlier attempt today (8d1169b, reverted in 64a6fbb) pulled names from a
second spreadsheet (the director's Tutoring Daily Sheet). This design instead
uses the roster the app already loads — no new config, no new sheet.

## Behavior

- In teacher texts only (`Student:` line and the multi-session block's student
  list), a student name that matches a Students row is printed as that row's
  **column A** (`StudentRow.calendar_name`).
- Unmatched or ambiguous names keep the calendar spelling — a wrong full name
  is worse than a short one.
- Student+parent texts are unchanged (they greet by Display Name).

## Touch points

- `src/message_builder.py` — `_build_teacher_messages` builds
  `student_labels: dict[raw name -> column A name]` via `roster.match_student`;
  `render_teacher_body` and `_teacher_sessions_block` take it and substitute.
- Tests: single and multi teacher bodies substitute; unmatched name untouched;
  student text still uses Display Name.

## Out of scope

Other sheets as name sources, changing student/parent texts, aliases beyond
what `match_student` already resolves.
