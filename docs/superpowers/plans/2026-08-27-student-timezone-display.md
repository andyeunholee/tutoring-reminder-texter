# Per-Student Timezone Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A student whose roster row says `CST` (or `MST`/`PST`) gets their student+parent reminder text with times shifted from EST and suffixed, e.g. `Time: 4:00 PM - 5:00 PM (CST)`.

**Architecture:** The Students tab gains a trailing "Time Zone" column that `build_roster` parses into `StudentRow.timezone` (validated; bad values become a visible load error, never a silent wrong time). `message_builder` shifts and suffixes times only in student-group bodies; teacher bodies never change. Fixed hour offsets from EST are correct year-round because US zones observe DST together.

**Tech Stack:** Python 3.14, pytest, Google Sheets API (headers only). Test command: `.venv\Scripts\python -m pytest tests -q` from the repo root.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-27-student-timezone-display-design.md`
- Recognized Time Zone values: `EST`, `CST`, `MST`, `PST` (case-insensitive, stripped); blank or `EST` = today's behavior (no shift, no suffix).
- Offsets from EST: CST -1h, MST -2h, PST -3h.
- Unrecognized value: warning appended to `roster.load_errors` (app.py already displays that list) and the student is treated as EST.
- `message_key` and all message identity/grouping logic must not change.
- Suffix format is exactly one space then `(CST)` etc., after the end time.

---

### Task 1: StudentRow.timezone parsed from the sheet

**Files:**
- Modify: `src/roster.py` (StudentRow dataclass ~line 59; build_roster student loop ~line 182)
- Test: `tests/test_roster_match.py`

**Interfaces:**
- Produces: `StudentRow.timezone: str` — `""`, `"EST"`, `"CST"`, `"MST"`, or `"PST"` (already stripped/uppercased). Task 2 consumes it.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_roster_match.py`:

```python
def test_student_timezone_column():
    rows = [["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", "", "cst"]]
    r = build_roster(TEACHERS, rows, [])
    assert r.match_student("Zena Kim").row.timezone == "CST"
    assert r.load_errors == []


def test_student_timezone_missing_column_is_est():
    r = build_roster(TEACHERS, STUDENTS, [])
    assert r.match_student("Jian Choi").row.timezone == ""


def test_student_timezone_typo_is_flagged_not_silent():
    rows = [["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", "", "CTS"]]
    r = build_roster(TEACHERS, rows, [])
    assert r.match_student("Zena Kim").row.timezone == ""
    assert any("CTS" in e and "Zena Kim" in e for e in r.load_errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_roster_match.py -q`
Expected: 3 failures — `TypeError`/`AttributeError` about `timezone` not existing.

- [ ] **Step 3: Implement.** In `src/roster.py`:

Add the field to the dataclass (after `active: bool`, keeping `notes` last is NOT required — but field order must match construction; put it after `notes`):

```python
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
```

Add a module constant near the top (after `_PHONE_SPLIT_RE`):

```python
_KNOWN_TIMEZONES = ("", "EST", "CST", "MST", "PST")
```

In `build_roster`'s student loop, before constructing `StudentRow`:

```python
        raw_tz = _get(row, 7)
        tz = raw_tz.strip().upper()
        if tz not in _KNOWN_TIMEZONES:
            roster.load_errors.append(
                f'Student "{name}" has an unrecognized Time Zone "{raw_tz}" '
                "(use CST, MST, or PST; blank = EST). Times left in EST."
            )
            tz = ""
```

and pass `timezone=tz` to the `StudentRow(...)` constructor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_roster_match.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/roster.py tests/test_roster_match.py
git commit -m "Read a per-student Time Zone column from the Students tab"
```

---

### Task 2: Shift and suffix times in student-group bodies

**Files:**
- Modify: `src/message_builder.py` (`_fmt_date_long`/`_time_range` ~lines 48-57, `_student_sessions_block` ~line 90, `render_student_body` ~line 125, `_build_student_messages` ~lines 227-323)
- Test: `tests/test_message_builder.py`

**Interfaces:**
- Consumes: `StudentRow.timezone` from Task 1.
- Produces: `render_student_body(display_name, events, org_name, tz="")`; internal `_time_range(ev, tz="")`, `_shift(dt, tz)`, `_TZ_SHIFT_FROM_EST` dict. Teacher paths keep calling `_time_range(ev)` with no tz.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_message_builder.py` (fixtures `TEACHERS`, `make_event`, `build_roster`, `build_messages` already exist there):

```python
CST_STUDENTS = STUDENTS + [
    ["Zena Kim", "Zena", "404-555-0208", "", "404-555-0209", "TRUE", "", "CST"],
]


def zena_roster():
    return build_roster(TEACHERS, CST_STUDENTS, [])


def test_cst_student_time_shifted_and_labeled():
    # Calendar 5-7 PM EST must read 4:00 PM - 6:00 PM (CST) in Zena's text.
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 17)
    msgs = build_messages([ev], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Time: 4:00 PM - 6:00 PM (CST)" in g.body


def test_cst_teacher_text_stays_est():
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 17)
    msgs = build_messages([ev], zena_roster())
    t = next(m for m in msgs if m.kind == "teacher")
    assert "5:00 PM - 7:00 PM" in t.body
    assert "(CST)" not in t.body


def test_cst_multi_session_lines_shifted():
    ev1 = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 13, "e1")
    ev2 = make_event("[TUT] Type: Online, Teacher Name: Jeongbeen teacher, Student Name: Zena Kim, Subject: English", 17, "e2")
    msgs = build_messages([ev1, ev2], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "- 12:00 PM - 2:00 PM (CST)" in g.body
    assert "- 4:00 PM - 6:00 PM (CST)" in g.body


def test_cst_shift_moves_the_date_too():
    # Midnight EST session belongs to the previous day in CST.
    ev = make_event("[TUT] Type: Online, Teacher Name: Joseph teacher, Student Name: Zena Kim, Subject: ACT Math", 0)
    msgs = build_messages([ev], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Friday, July 31" in g.body


def test_est_student_body_unchanged():
    ev = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15)
    msgs = build_messages([ev], zena_roster())
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Time: 3:00 PM - 5:00 PM" in g.body
    assert "(" not in g.body.split("Time:")[1].splitlines()[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_message_builder.py -q`
Expected: the four CST tests fail (times unshifted, no suffix); `test_est_student_body_unchanged` passes.

- [ ] **Step 3: Implement.** In `src/message_builder.py`:

Add near the imports:

```python
from datetime import timedelta
```

Replace the formatting helpers (`_fmt_date_long` stays as is) and add the shift machinery:

```python
# Hours to add to an EST clock time. Fixed offsets are safe year-round:
# the US zones enter and leave daylight saving together.
_TZ_SHIFT_FROM_EST = {"CST": -1, "MST": -2, "PST": -3}


def _shift(dt, tz: str):
    hours = _TZ_SHIFT_FROM_EST.get(tz)
    return dt + timedelta(hours=hours) if hours else dt


def _time_range(ev: TutEvent, tz: str = "") -> str:
    suffix = f" ({tz})" if tz in _TZ_SHIFT_FROM_EST else ""
    return f"{_fmt_time(_shift(ev.start, tz))} - {_fmt_time(_shift(ev.end, tz))}{suffix}"
```

`_student_sessions_block` gains the parameter and passes it through:

```python
def _student_sessions_block(events: list[TutEvent], tz: str = "") -> str:
    lines = []
    for ev in events:
        line = (
            f"- {_time_range(ev, tz)} - {ev.parsed.subject_clean or ev.subject}"
            f" with {ev.teacher_name} ({ev.parsed.session_type})"
        )
        lines.append(line)
        if ev.parsed.is_online and ev.meet_link:
            lines.append(f"  Link: {ev.meet_link}")
    return "\n".join(lines)
```

`render_student_body` gains `tz` and shifts the date line with the same rule:

```python
def render_student_body(display_name: str, events: list[TutEvent], org_name: str, tz: str = "") -> str:
    if len(events) == 1:
        ev = events[0]
        return _tidy(templates.STUDENT_GROUP_SINGLE.format(
            recipient_name=display_name,
            org_name=org_name,
            date_long=_fmt_date_long(_shift(ev.start, tz)),
            time_range=_time_range(ev, tz),
            teacher_name=ev.teacher_name,
            subject=ev.parsed.subject_clean or ev.subject,
            location_line=_location_line(ev),
            meet_line=_meet_line(ev),
        ))
    return _tidy(templates.STUDENT_GROUP_MULTI.format(
        recipient_name=display_name,
        org_name=org_name,
        date_long=_fmt_date_long(_shift(events[0].start, tz)),
        session_count=len(events),
        sessions_block=_student_sessions_block(events, tz),
    ))
```

In `_build_student_messages`, capture the timezone of the first matched student
that has one. Inside the `for raw_name in ev.student_names:` loop the matched
branch starts with `row = match.row`; initialize `tz = ""` next to
`recipients: list[Recipient] = []` and inside the matched branch add:

```python
                if not tz and row.timezone in _TZ_SHIFT_FROM_EST:
                    tz = row.timezone
```

Add `"tz": tz,` to the `prelim.append({...})` dict. In the merge loop (the
`groups.setdefault` block), after `g["events"].append(...)` add:

```python
        if not g["tz"]:
            g["tz"] = p["tz"]
```

And build the body with it:

```python
        body = render_student_body(g["display"], evs, org_name, tz=g["tz"])
```

Teacher paths are untouched: `render_teacher_body` still calls `_time_range(ev)`.

- [ ] **Step 4: Run the full suite**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all pass (existing message_key digests unaffected — identity inputs unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/message_builder.py tests/test_message_builder.py
git commit -m "Show a CST/MST/PST student's text times in their own zone"
```

---

### Task 3: Teacher full names in student texts

**Files:**
- Modify: `src/roster.py` (TeacherRow dataclass ~line 50; build_roster teacher loop ~line 166)
- Modify: `src/message_builder.py` (`_student_sessions_block`, `render_student_body`, `_build_student_messages`)
- Test: `tests/test_message_builder.py`, `tests/test_roster_match.py`

**Interfaces:**
- Consumes: `render_student_body(display_name, events, org_name, tz="")` from Task 2.
- Produces: `TeacherRow.full_name: str`; `render_student_body(..., teacher_labels=None)` where `teacher_labels: dict[str, str]` maps raw `ev.teacher_name` → printed name.

- [ ] **Step 1: Write the failing tests.** In `tests/test_roster_match.py`:

```python
def test_teacher_full_name_column():
    rows = [["Joseph", "Joseph", "404-555-0102", "TRUE", "", "Mr. Joseph O'Hailey"]]
    r = build_roster(rows, STUDENTS, [])
    assert r.match_teacher("Joseph teacher").row.full_name == "Mr. Joseph O'Hailey"
```

In `tests/test_message_builder.py`:

```python
FULL_NAME_TEACHERS = [
    ["Joseph", "Joseph", "404-555-0102", "TRUE", "", "Mr. Joseph O'Hailey"],
    ["Jeongbeen", "Jeongbeen", "404-555-0101", "TRUE", ""],
]


def test_student_text_uses_teacher_full_name():
    ev = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 15)
    msgs = build_messages([ev], build_roster(FULL_NAME_TEACHERS, STUDENTS, []))
    g = next(m for m in msgs if m.kind == "student_group")
    assert "Teacher: Mr. Joseph O'Hailey" in g.body
    t = next(m for m in msgs if m.kind == "teacher")
    assert "Hi Joseph," in t.body        # the teacher's own greeting is untouched


def test_student_multi_session_uses_teacher_full_name():
    ev1 = make_event("[TUT] Type: In-Person, Teacher Name: Joseph teacher, Student Name: Jian Choi, Subject: Math", 13, "e1")
    ev2 = make_event("[TUT] Type: In-Person, Teacher Name: Jeongbeen teacher, Student Name: Jian Choi, Subject: Bio", 15, "e2")
    msgs = build_messages([ev1, ev2], build_roster(FULL_NAME_TEACHERS, STUDENTS, []))
    g = next(m for m in msgs if m.kind == "student_group")
    assert "with Mr. Joseph O'Hailey" in g.body
    assert "with Jeongbeen" in g.body    # blank Full Name falls back to the calendar name
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_roster_match.py tests/test_message_builder.py -q`
Expected: the three new tests fail (`full_name` missing / body says "Teacher: Joseph").

- [ ] **Step 3: Implement.** `src/roster.py` — extend the dataclass and the loader:

```python
@dataclass(frozen=True)
class TeacherRow:
    calendar_name: str
    display_name: str
    phone: str
    active: bool
    notes: str = ""
    full_name: str = ""   # exact text for student texts, e.g. "Mr. Joseph O'Hailey"
```

and in `build_roster`'s teacher loop pass `full_name=_get(row, 5)`.

`src/message_builder.py` — helper next to `_time_range`:

```python
def _teacher_label(ev: TutEvent, teacher_labels: dict[str, str] | None) -> str:
    if teacher_labels:
        return teacher_labels.get(ev.teacher_name) or ev.teacher_name
    return ev.teacher_name
```

`_student_sessions_block(events, tz="", teacher_labels=None)` uses
`f" with {_teacher_label(ev, teacher_labels)} ({ev.parsed.session_type})"`.
`render_student_body(..., tz="", teacher_labels=None)` passes
`teacher_name=_teacher_label(ev, teacher_labels)` in the single template and
`teacher_labels` through to the block. In `_build_student_messages`, before the
prelim loop:

```python
    teacher_labels: dict[str, str] = {}
    for ev in events:
        raw = ev.teacher_name
        if raw and raw not in teacher_labels:
            tmatch = roster.match_teacher(raw)
            if tmatch.matched and tmatch.row.full_name:
                teacher_labels[raw] = tmatch.row.full_name
```

and at the end: `body = render_student_body(g["display"], evs, org_name, tz=g["tz"], teacher_labels=teacher_labels)`.

- [ ] **Step 4: Run the full suite**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/roster.py src/message_builder.py tests/test_roster_match.py tests/test_message_builder.py
git commit -m "Address teachers by their full name in student texts"
```

---

### Task 4: Sheet headers, README, and push

**Files:**
- Modify: `scripts/create_roster_sheet.py:31-32` (STUDENT_HEADERS), `scripts/create_roster_sheet.py:89` (new-student row template)
- Modify: `README.md` (roster section, after the Display Name paragraph)

**Interfaces:**
- Consumes: nothing from other tasks (independent of code paths).
- Produces: new sheets carry the header; docs tell the owner how to use the column.

- [ ] **Step 1: Extend the headers and the blank-row templates**

```python
TEACHER_HEADERS = ["Teacher Name (as in calendar)", "Display Name", "Phone", "Active", "Notes",
                   "Full Name (in student texts)"]
STUDENT_HEADERS = ["Student Name (as in calendar)", "Display Name", "Student Phone",
                   "Parent Name", "Parent Phone", "Active", "Notes", "Time Zone"]
```

and in the creation batch (lines ~87-89) give new rows the extra blank cell:

```python
             "values": [TEACHER_HEADERS] + [[t, t, "", "TRUE", "", ""] for t in teachers]},
...
             "values": [STUDENT_HEADERS] + [[s, "", "", "", "", "TRUE", "", ""] for s in students]},
```

- [ ] **Step 2: README bullet.** In the roster-sheet setup section (after the
Display Name paragraph ending "괄호만 뗀 이름을 씁니다."), add:

```markdown
   다른 시간대에 사는 학생은 Students 탭 맨 끝 **Time Zone** 칸에 `CST`,
   `MST`, `PST` 중 하나를 적으세요. 그 학생+부모님 문자의 시간만 그 시간대로
   바뀌어 표시됩니다 (예: 캘린더 5:00 PM → `4:00 PM (CST)`). 비워두면 EST
   그대로이고, 선생님 문자는 항상 EST입니다. 기존 시트에는 H1 칸에
   `Time Zone`이라고 머리글을 직접 한 번 적어주면 됩니다.

   학생 문자에 선생님을 정식 호칭으로 쓰고 싶으면 Teachers 탭 맨 끝
   **Full Name** 칸에 표기할 이름 그대로 적으세요 (예: `Mr. Joseph O'Hailey`).
   학생+부모님 문자의 `Teacher:` 줄에만 쓰이고, 선생님 본인에게 가는 문자의
   인사말은 Display Name을 그대로 씁니다. 비워두면 캘린더 이름이 쓰입니다.
```

- [ ] **Step 3: Full suite once more**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 4: Commit and push**

```bash
git add scripts/create_roster_sheet.py README.md docs/superpowers/plans/2026-08-27-student-timezone-display.md
git commit -m "Document the Time Zone roster column and add it to new sheets"
git push
```

---

### Task 5: Wire up the live sheet (manual, with the owner)

Not code. The existing spreadsheet needs, one time:
- **Students** tab: `H1` = `Time Zone`, Zena Kim's row column H = `CST`
- **Teachers** tab: `F1` = `Full Name (in student texts)`, then the owner fills
  each teacher's formal name (only the owner knows them)

Open `https://docs.google.com/spreadsheets/d/<ROSTER_SPREADSHEET_ID>/edit`
(ID in `.env`). Then in the app press **Search calendar** again and check the
preview shows `(CST)` on Zena's message only.
