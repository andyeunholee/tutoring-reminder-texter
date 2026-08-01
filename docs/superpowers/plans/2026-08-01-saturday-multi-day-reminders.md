# Saturday Multi-Day Reminders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A run started on a Saturday prepares reminder messages for Sunday, Monday and Tuesday — each day rendered and sent as its own set of messages — while every other weekday keeps covering tomorrow only.

**Architecture:** A new pure module `src/coverage_window.py` decides which dates a run covers. `app.py` loops those dates, calling the existing single-day calendar fetch once per date and calling `build_messages` once per date so that session merging and the date line in each message stay inside one day. `message_key` gains an optional `day_tag` so the same person on two dates produces two independent messages. `src/calendar_service.py` and `src/templates.py` are not modified.

**Tech Stack:** Python 3, Streamlit, Google Calendar API (`googleapiclient`), pytest.

**Spec:** `docs/superpowers/specs/2026-07-31-saturday-multi-day-reminders-design.md`

## Global Constraints

- Do not modify `src/templates.py`. Messages never span more than one date, so the existing `{date_long}` header stays correct.
- Do not modify `src/calendar_service.py`. Multi-day fetching is a loop over the existing `list_tut_events_on(day)`.
- Do not modify `daily_reminder.bat`, `run_app.bat`, `setup_daily_task.bat`, or the registered Windows task. The Saturday decision is made by the app at run time.
- Messages are never sent automatically. Every change must preserve the review-then-press-send flow.
- Saturday is `date.weekday() == 5`. Monday is 0.
- `?days=` is clamped to 1–7.
- Test command is `.venv\Scripts\python -m pytest tests -q` (PowerShell, from the project root).
- Commit messages in this repo are plain imperative sentences, not Conventional Commits. Match the existing style (`git log --oneline` shows `Accept several numbers in the test-redirect box`). End every commit message with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- Work happens on branch `saturday-multi-day`, which starts at commit `d8c497c`.
- Line numbers in "Modify" lists are as of commit `d8c497c` and shift as earlier tasks land. Anchor on the quoted code, not the number.

---

### Task 1: Coverage window module

Decides which dates a run covers, and how the `?date=` / `?days=` query parameters override that. Pure functions, no I/O, no Streamlit import — so it is fully unit-testable.

**Files:**
- Create: `src/coverage_window.py`
- Create: `tests/test_coverage_window.py`
- Commit also: `docs/superpowers/specs/2026-07-31-saturday-multi-day-reminders-design.md`, `docs/superpowers/plans/2026-08-01-saturday-multi-day-reminders.md` (both currently untracked)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `default_span(today: date) -> int` — 3 on Saturday, else 1.
  - `coverage_days(first_day: date, span: int) -> list[date]` — consecutive dates, always at least one.
  - `resolve_window(raw_date: str | None, raw_days: str | None, today: date) -> tuple[date, int]` — returns `(first_day, span)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_coverage_window.py`:

```python
from datetime import date

import pytest

from src.coverage_window import coverage_days, default_span, resolve_window

# 2026-07-27 is a Monday, 2026-08-01 a Saturday, 2026-08-02 a Sunday.
SATURDAY = date(2026, 8, 1)
FRIDAY = date(2026, 7, 31)
SUNDAY = date(2026, 8, 2)
MONDAY = date(2026, 8, 3)
TUESDAY = date(2026, 8, 4)


def test_saturday_covers_three_days():
    assert default_span(SATURDAY) == 3


@pytest.mark.parametrize("day", [
    date(2026, 7, 27),  # Mon
    date(2026, 7, 28),  # Tue
    date(2026, 7, 29),  # Wed
    date(2026, 7, 30),  # Thu
    FRIDAY,
    SUNDAY,
])
def test_other_weekdays_cover_one_day(day):
    assert default_span(day) == 1


def test_coverage_days_are_consecutive():
    assert coverage_days(SUNDAY, 3) == [SUNDAY, MONDAY, TUESDAY]


def test_coverage_days_of_one():
    assert coverage_days(SUNDAY, 1) == [SUNDAY]


@pytest.mark.parametrize("span", [0, -3])
def test_span_below_one_still_returns_one_day(span):
    assert coverage_days(SUNDAY, span) == [SUNDAY]


def test_saturday_run_with_no_params_covers_sunday_through_tuesday():
    first_day, span = resolve_window(None, None, SATURDAY)
    assert (first_day, span) == (SUNDAY, 3)
    assert coverage_days(first_day, span) == [SUNDAY, MONDAY, TUESDAY]


def test_weekday_run_with_no_params_covers_tomorrow_only():
    assert resolve_window(None, None, FRIDAY) == (SATURDAY, 1)


def test_explicit_date_covers_that_day_only_even_on_saturday():
    assert resolve_window("2026-08-03", None, SATURDAY) == (MONDAY, 1)


def test_days_param_wins_over_explicit_date():
    assert resolve_window("2026-08-02", "3", SATURDAY) == (SUNDAY, 3)


def test_unparsable_params_fall_back_to_defaults():
    assert resolve_window("not-a-date", "abc", SATURDAY) == (SUNDAY, 3)


@pytest.mark.parametrize("raw_days, expected", [("99", 7), ("0", 1), ("-2", 1)])
def test_days_param_is_clamped(raw_days, expected):
    assert resolve_window(None, raw_days, FRIDAY)[1] == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_coverage_window.py -q`

Expected: collection error — `ModuleNotFoundError: No module named 'src.coverage_window'`

- [ ] **Step 3: Write the implementation**

Create `src/coverage_window.py`:

```python
"""Which dates one run of the reminder app covers. Pure logic, no I/O."""

from __future__ import annotations

from datetime import date, timedelta

SATURDAY = 5      # date.weekday(): Mon=0 … Sat=5, Sun=6
MAX_SPAN = 7

# A Saturday run reaches Sunday, Monday and Tuesday, so the weekend sitting
# prepares the start of the week in one go. Every other day covers tomorrow,
# which is what the daily 2pm task has always done.
SATURDAY_SPAN = 3


def default_span(today: date) -> int:
    """How many days a run started on `today` should cover."""
    return SATURDAY_SPAN if today.weekday() == SATURDAY else 1


def coverage_days(first_day: date, span: int) -> list[date]:
    """`span` consecutive dates starting at `first_day`. Never fewer than one."""
    return [first_day + timedelta(days=i) for i in range(max(1, span))]


def resolve_window(raw_date, raw_days, today: date) -> tuple[date, int]:
    """Turn the ?date= / ?days= query params into (first_day, span).

    Precedence, first match wins:
      1. ?days=N sets the span, even alongside ?date=
      2. ?date= alone means that single day
      3. neither -> tomorrow, for default_span(today) days

    Unparsable values are treated as absent rather than raising, so a typo in
    the address bar degrades to the normal view instead of an error page.
    """
    explicit_day = None
    if raw_date:
        try:
            explicit_day = date.fromisoformat(str(raw_date))
        except ValueError:
            explicit_day = None

    span = None
    if raw_days:
        try:
            span = max(1, min(MAX_SPAN, int(str(raw_days))))
        except ValueError:
            span = None

    first_day = explicit_day or (today + timedelta(days=1))
    if span is None:
        span = 1 if explicit_day else default_span(today)
    return first_day, span
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_coverage_window.py -q`

Expected: PASS — 18 passed

- [ ] **Step 5: Run the whole suite to confirm nothing regressed**

Run: `.venv\Scripts\python -m pytest tests -q`

Expected: PASS — all existing tests still green

- [ ] **Step 6: Commit**

```bash
git add src/coverage_window.py tests/test_coverage_window.py docs/superpowers
git commit -m "Decide the covered dates in one place, three days on Saturday

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Date-scoped message keys

`message_key` currently hashes `kind | identity | phones`. The same teacher on Sunday and on Tuesday therefore gets the same key, and `app.py` indexes the draft box, the send checkbox and the send result by that key — so the two messages would share one editor and one result row. Adding an optional `day_tag` fixes this. An empty `day_tag` must leave the hash byte-identical so nothing else shifts.

**Files:**
- Modify: `src/message_builder.py:39-41` (`message_key`), `:143-157` (`build_messages`), `:160` and `:204-206` (`_build_teacher_messages`), `:220` and `:302-304` (`_build_student_messages`)
- Test: `tests/test_message_builder.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `message_key(kind: str, identity: str, phones: list[str], day_tag: str = "") -> str`
  - `build_messages(events, roster, *, merge_sessions_per_recipient=True, include_cancelled=False, org_name="Elite Prep", day_tag: str = "") -> list[OutboundMessage]`

- [ ] **Step 1: Record the current keys so backward compatibility is testable**

Run this from the project root and keep the output — the two digests go into the test in Step 2:

```bash
.venv/Scripts/python -c "from src.message_builder import message_key; print(message_key('teacher','joseph',['404-555-0102'])); print(message_key('student_group','andrew',['404-555-0202','404-555-0203']))"
```

Expected: two 10-character hex strings, one per line.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_message_builder.py`. Replace `PASTE_TEACHER_DIGEST` and `PASTE_GROUP_DIGEST` with the two values printed in Step 1 — that is what pins the hash against accidental change.

```python
def make_event_on(day, summary, hour, eid="e1"):
    """Same as make_event but on an explicit date, for multi-day tests."""
    return TutEvent(
        event_id=eid,
        recurring_event_id=None,
        raw_summary=summary,
        start=datetime(day.year, day.month, day.day, hour, 0, tzinfo=TZ),
        end=datetime(day.year, day.month, day.day, hour + 2, 0, tzinfo=TZ),
        html_link="",
        meet_link=None,
        parsed=parse_tut_title(summary),
    )


JOSEPH_ANDREW = ("[TUT] Type: In-Person, Teacher Name: Joseph teacher, "
                 "Student Name: Kyuheon (Andrew) Ahn, Subject: English")


def test_empty_day_tag_keeps_the_existing_keys():
    # app.py indexes widgets by these digests; changing them silently would
    # orphan every in-flight draft.
    assert message_key("teacher", "joseph", ["404-555-0102"]) == "PASTE_TEACHER_DIGEST"
    assert message_key("teacher", "joseph", ["404-555-0102"], "") == "PASTE_TEACHER_DIGEST"
    assert message_key(
        "student_group", "andrew", ["404-555-0202", "404-555-0203"]
    ) == "PASTE_GROUP_DIGEST"


def test_day_tag_changes_the_key():
    a = message_key("teacher", "joseph", ["404-555-0102"], "2026-08-02")
    b = message_key("teacher", "joseph", ["404-555-0102"], "2026-08-03")
    assert a != b
    assert a != message_key("teacher", "joseph", ["404-555-0102"])


def test_same_person_on_two_days_gets_two_independent_messages():
    sun = build_messages([make_event_on(date(2026, 8, 2), JOSEPH_ANDREW, 13, "e1")],
                         roster(), day_tag="2026-08-02")
    mon = build_messages([make_event_on(date(2026, 8, 3), JOSEPH_ANDREW, 13, "e2")],
                         roster(), day_tag="2026-08-03")
    assert {m.key for m in sun}.isdisjoint({m.key for m in mon})


def test_per_day_building_keeps_each_date_line_correct():
    sun = build_messages([make_event_on(date(2026, 8, 2), JOSEPH_ANDREW, 13, "e1")],
                         roster(), day_tag="2026-08-02")
    mon = build_messages([make_event_on(date(2026, 8, 3), JOSEPH_ANDREW, 15, "e2")],
                         roster(), day_tag="2026-08-03")
    t_sun = next(m for m in sun if m.kind == "teacher")
    t_mon = next(m for m in mon if m.kind == "teacher")
    assert "Sunday, August 2" in t_sun.body
    assert "Monday, August 3" in t_mon.body
    # neither message mentions the other day
    assert "August 3" not in t_sun.body
    assert "August 2" not in t_mon.body
```

Add the imports this needs to the top of the file:

```python
from datetime import date, datetime
```

(the existing line is `from datetime import datetime`), and extend the
`src.message_builder` import line to:

```python
from src.message_builder import build_messages, message_key
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_message_builder.py -q`

Expected: FAIL — `TypeError: message_key() takes 3 positional arguments but 4 were given` and `TypeError: build_messages() got an unexpected keyword argument 'day_tag'`

- [ ] **Step 4: Thread `day_tag` through message_builder**

In `src/message_builder.py`, replace `message_key`:

```python
def message_key(kind: str, identity: str, phones: list[str], day_tag: str = "") -> str:
    basis = f"{kind}|{identity.casefold()}|{','.join(sorted(phones))}"
    if day_tag:
        # Without the date, the same teacher on two covered days collides and
        # the two messages share one draft box and one result row in app.py.
        basis = f"{day_tag}|{basis}"
    return hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]
```

Change the `build_messages` signature and the two calls it makes:

```python
def build_messages(
    events: list[TutEvent],
    roster: Roster,
    *,
    merge_sessions_per_recipient: bool = True,
    include_cancelled: bool = False,
    org_name: str = "Elite Prep",
    day_tag: str = "",
) -> list[OutboundMessage]:
    active = [e for e in events if include_cancelled or not e.is_cancelled]
    active.sort(key=lambda e: e.start)

    messages: list[OutboundMessage] = []
    messages.extend(
        _build_teacher_messages(active, roster, merge_sessions_per_recipient, org_name, day_tag))
    messages.extend(
        _build_student_messages(active, roster, merge_sessions_per_recipient, org_name, day_tag))
    return messages
```

Change both helper signatures:

```python
def _build_teacher_messages(events, roster, merge, org_name, day_tag="") -> list[OutboundMessage]:
```

```python
def _build_student_messages(events, roster, merge, org_name, day_tag="") -> list[OutboundMessage]:
```

And both `message_key(...)` calls inside them:

```python
            key=message_key("teacher", match.norm_key or raw_name, phones, day_tag),
```

```python
            key=message_key("student_group", g["identity_norm"], phones, day_tag),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_message_builder.py -q`

Expected: PASS

- [ ] **Step 6: Run the whole suite**

Run: `.venv\Scripts\python -m pytest tests -q`

Expected: PASS — all green

- [ ] **Step 7: Commit**

```bash
git add src/message_builder.py tests/test_message_builder.py
git commit -m "Key each message by its date so one person can appear on two days

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Multi-day search and rendering in the app

Replaces the single `day` with a list of covered dates, end to end: query params, inputs, fetch, message building, both screens. `app.py` must stay runnable, so the plumbing and the rendering that reads it change together.

**Files:**
- Modify: `app.py` — `:13` (imports), `:70-77` (session state), `:129-183` (date + search), `:201-212` (message building), `:224-260` (screen 2), `:263-279` (screen 3 preamble), `:295-320` (review form)

**Interfaces:**
- Consumes: `resolve_window`, `coverage_days` from Task 1; `build_messages(..., day_tag=...)` from Task 2.
- Produces:
  - `ss.day_results: list[dict] | None` — each `{"day": date, "events": list[TutEvent], "total_scanned": int}`, `None` before the first search.
  - `messages_by_day: list[tuple[date, list[OutboundMessage]]]` — rebuilt every run, consumed by Task 4.
  - `ss.messages: list[OutboundMessage]` — flat across all days; the send path keeps using this unchanged.

- [ ] **Step 1: Fix the imports**

In `app.py`, below `from src.calendar_service import TutoringCalendarService`, add:

```python
from src.coverage_window import coverage_days, resolve_window
```

`timedelta` becomes unused once `requested_day()` goes away in Step 3, so narrow
line 13:

```python
from datetime import date, timedelta
```

to:

```python
from datetime import date
```

- [ ] **Step 2: Replace the session-state defaults**

Replace `app.py:70-77`:

```python
ss = st.session_state
ss.setdefault("events", None)
ss.setdefault("total_scanned", 0)
ss.setdefault("messages", [])
ss.setdefault("results", {})       # key -> {"status": ..., "error": ...}
ss.setdefault("run_log", [])
ss.setdefault("searched_day", None)
ss.setdefault("autosearch_done", False)
```

with:

```python
ss = st.session_state
# day_results: list of {"day": date, "events": [...], "total_scanned": int}
# None means "no search has been run yet".
ss.setdefault("day_results", None)
ss.setdefault("messages", [])
ss.setdefault("results", {})       # key -> {"status": ..., "error": ...}
ss.setdefault("run_log", [])
ss.setdefault("autosearch_done", False)
```

- [ ] **Step 3: Replace the date picker and the search block**

Replace everything from `def requested_day() -> date:` (`app.py:133`) through the `day = ss.searched_day` line (`app.py:183`) with:

```python
first_day, default_days = resolve_window(
    st.query_params.get("date"),
    st.query_params.get("days"),
    date.today(),
)

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    start_day = st.date_input("First session date", value=first_day)
with col2:
    span = st.number_input("Days to cover", min_value=1, max_value=7,
                           value=default_days, step=1,
                           help="A Saturday run defaults to 3 so Sunday, Monday "
                                "and Tuesday can be prepared in one sitting.")
with col3:
    st.write("")
    st.write("")
    search_clicked = st.button("🔍 Search calendar", type="primary", use_container_width=True)

days = coverage_days(start_day, int(span))
if len(days) > 1:
    st.caption("Covering " + "  ·  ".join(f"{d:%a %b %d}" for d in days))

# ?auto=1 (used by the 2pm scheduled task) searches straight away, so the page
# is already showing the upcoming messages when it appears on screen.
auto_search = (str(st.query_params.get("auto", "")).lower() in ("1", "true", "yes")
               and not ss.autosearch_done)
if auto_search:
    ss.autosearch_done = True

do_search = search_clicked or auto_search

if do_search:
    if not spreadsheet_id:
        st.error("Set the roster spreadsheet ID first (sidebar). "
                 "Run `python scripts/create_roster_sheet.py` if you don't have one.")
        st.stop()
    try:
        svc = TutoringCalendarService(google_creds(), config.CALENDAR_ID, config.LOCAL_TZ)
        # One fetch per day. Three calls a week costs nothing and keeps the
        # per-day grouping that the messages and the review list need.
        fetched = []
        for d in days:
            events, total = svc.list_tut_events_on(d)
            fetched.append({"day": d, "events": events, "total_scanned": total})
    except Exception as e:
        # Deliberately all-or-nothing: a partial result would make "no sessions
        # on Sunday" indistinguishable from "Sunday's fetch failed".
        st.error(f"Calendar fetch failed: {e}")
        st.stop()
    ss.day_results = fetched
    ss.results = {}
    ss.run_log = []

if ss.day_results is None:
    st.info("Pick a date and click **Search calendar**.")
    st.stop()
```

- [ ] **Step 4: Build messages one day at a time**

Replace `app.py:201-212` (from `messages = build_messages(` through `ss.messages = messages`) with:

```python
messages_by_day: list[tuple[date, list]] = []
for r in ss.day_results:
    day_msgs = build_messages(
        r["events"],
        roster,
        merge_sessions_per_recipient=merge_toggle,
        include_cancelled=include_cancelled,
        org_name=config.ORG_NAME,
        day_tag=r["day"].isoformat(),
    )
    if not send_teachers:
        day_msgs = [m for m in day_msgs if m.kind != "teacher"]
    if not send_students:
        day_msgs = [m for m in day_msgs if m.kind != "student_group"]
    messages_by_day.append((r["day"], day_msgs))

messages = [m for _, day_msgs in messages_by_day for m in day_msgs]
ss.messages = messages
```

The `valid_keys` / draft pruning block that follows (`app.py:214-221`) works on the
flat `messages` list and needs no change.

- [ ] **Step 5: Render screen 2 per day**

Replace `app.py:224-260` (from `active_events = [e for e in events ...]` through the end of the raw-titles expander) with:

```python
for r in ss.day_results:
    d, day_events = r["day"], r["events"]
    active_events = [e for e in day_events if not e.is_cancelled]
    cancelled_events = [e for e in day_events if e.is_cancelled]

    st.subheader(f"{d:%A}, {d:%B} {d.day} — {len(active_events)} tutoring session(s)")
    st.caption(f"{r['total_scanned']} calendar events scanned, {len(day_events)} with [TUT].")

    if not day_events:
        st.info(f"No [TUT] events found on {d}.")
        continue

    rows = []
    for e in active_events:
        rows.append({
            "Time": f"{e.start:%I:%M %p} - {e.end:%I:%M %p}",
            "Type": e.parsed.session_type,
            "Teacher": e.teacher_name,
            "Student(s)": ", ".join(e.student_names),
            "Subject": e.subject,
        })
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if cancelled_events and not include_cancelled:
        with st.expander(f"🚫 {len(cancelled_events)} cancelled event(s) skipped — {d:%b %d}"):
            for e in cancelled_events:
                st.text(f"{e.start:%I:%M %p}  [{e.parsed.cancel_marker}]  {e.raw_summary}")

    with st.expander(f"Raw titles (parser audit) — {d:%b %d}"):
        for e in day_events:
            st.text(e.raw_summary)
            st.caption(
                f"→ teacher: {e.teacher_name!r} | students: {e.student_names!r} | "
                f"subject: {e.subject!r} | type: {e.parsed.session_type!r} | "
                f"cancelled: {e.is_cancelled} | warnings: {e.parsed.warnings}"
            )

# Only give up when every covered day is empty — one empty Sunday must not
# hide Monday and Tuesday.
if not any(r["events"] for r in ss.day_results):
    st.stop()
```

- [ ] **Step 6: Widen the "nothing to send" guard**

In screen 3, replace `app.py:277-279`:

```python
if not messages:
    st.info("Nothing to send for this day with the current toggles.")
    st.stop()
```

with:

```python
if not messages:
    st.info("Nothing to send for these dates with the current toggles.")
    st.stop()
```

- [ ] **Step 7: Group the review form by day**

Replace the whole `with st.form("review"):` block (`app.py:295-328`, up to and
including the `st.form_submit_button(...)` call) with this. The per-message body is
identical to what is there now, just indented one level deeper under the new day loop:

```python
with st.form("review"):
    for d, day_msgs in messages_by_day:
        if not day_msgs:
            continue
        st.markdown(f"### {d:%A}, {d:%B} {d.day}")
        for m in day_msgs:
            with st.container(border=True):
                head_l, head_r = st.columns([5, 2])
                with head_l:
                    sessions = f"{len(m.events)} session(s)"
                    st.checkbox(
                        f"**{KIND_LABEL.get(m.kind, m.kind)} · {m.identity}** · {sessions}",
                        key=f"send_{m.key}",
                        disabled=m.blocked,
                    )
                with head_r:
                    for b in m.badges:
                        st.caption(f"🔶 {b}")
                    if m.is_cancelled:
                        st.caption("🚫 CANCELLED event")
                if m.recipients:
                    st.caption("To: " + " · ".join(f"{r.label} {r.phone}" for r in m.recipients)
                               + ("  → 그룹 문자" if m.group_mode else "  → 1:1"))
                for reason in m.block_reasons:
                    st.markdown(f":red[⚠️ {reason}]")
                st.text_area("Message", key=f"draft_{m.key}", height=170,
                             label_visibility="collapsed", disabled=m.blocked)
                with st.expander("Source events"):
                    for e in m.events:
                        st.text(f"{e.start:%I:%M %p}  {e.raw_summary}")

    n_selected = sum(
        1 for m in messages if not m.blocked and ss.get(f"send_{m.key}", False))
    submitted = st.form_submit_button(
        f"📨 Send {n_selected} selected message(s)"
        + (f" ({len(blocked)} blocked)" if blocked else ""),
        type="primary",
    )
```

`n_selected` still counts across the flat `messages` list, so one submit button
covers every day.

- [ ] **Step 8: Run the test suite**

Run: `.venv\Scripts\python -m pytest tests -q`

Expected: PASS — `app.py` has no unit tests, but this catches an accidental import break.

- [ ] **Step 9: Check the file parses**

Run: `.venv\Scripts\python -c "import ast,pathlib; ast.parse(pathlib.Path('app.py').read_text(encoding='utf-8')); print('ok')"`

Expected: `ok`

- [ ] **Step 10: Verify in the running app**

Stop any running instance (close the black console window), then start it from
the project root:

```bash
.venv/Scripts/python -m streamlit run app.py
```

Open `http://localhost:8501/?date=2026-08-02&days=3&auto=1` and confirm:
1. Three dated sections appear — Sunday Aug 2, Monday Aug 3, Tuesday Aug 4.
2. A day with no sessions shows "No [TUT] events found" and the other days still render.
3. If one person appears on two days, editing one draft box leaves the other unchanged.
4. Each message's `Date:` line matches the section it sits under.

Leave the app running for Task 4.

- [ ] **Step 11: Commit**

```bash
git add app.py
git commit -m "Cover several days in one sitting, grouped by date

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Per-day selection and a date column in the results

Convenience for the Saturday case: selecting a whole day at once, and telling apart
two result rows for the same person. Independently rejectable — Task 3 is already
usable without it.

**Files:**
- Modify: `app.py` — the button row before `with st.form("review")`, and the results table

**Interfaces:**
- Consumes: `messages_by_day` from Task 3.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add per-day select buttons above the form**

Streamlit forbids ordinary buttons inside `st.form`, so these must sit above it.
Insert this immediately after the existing global `Select all` / `Deselect all` /
`Reset drafts` three-column row and before `with st.form("review"):`:

```python
# Per-day buttons must live outside the form — Streamlit only allows
# st.form_submit_button inside one.
if len(messages_by_day) > 1:
    for d, day_msgs in messages_by_day:
        if not day_msgs:
            continue
        lbl, b_sel, b_desel = st.columns([3, 1, 1])
        lbl.markdown(f"**{d:%A, %b %d}** — {len(day_msgs)} message(s)")
        if b_sel.button("Select all", key=f"selall_{d.isoformat()}",
                        use_container_width=True):
            for m in day_msgs:
                if not m.blocked:
                    ss[f"send_{m.key}"] = True
        if b_desel.button("Deselect all", key=f"deselall_{d.isoformat()}",
                          use_container_width=True):
            for m in day_msgs:
                ss[f"send_{m.key}"] = False
```

These run before the checkboxes are instantiated, so writing `ss[f"send_…"]` here
lands before the widget reads it — the same pattern the existing global buttons use.

- [ ] **Step 2: Add a Date column to the results table**

In the results section, replace:

```python
    by_key = {m.key: m for m in messages}
    res_rows = []
    for key, r in ss.results.items():
        m = by_key.get(key)
        res_rows.append({
            "Message": f"{KIND_LABEL.get(m.kind, '?')} · {m.identity}" if m else key,
            "Status": r["status"],
            "Error": r.get("error") or "",
        })
```

with:

```python
    by_key = {m.key: m for m in messages}
    day_by_key = {m.key: d for d, day_msgs in messages_by_day for m in day_msgs}
    res_rows = []
    for key, r in ss.results.items():
        m = by_key.get(key)
        d = day_by_key.get(key)
        res_rows.append({
            "Date": f"{d:%a %b %d}" if d else "",
            "Message": f"{KIND_LABEL.get(m.kind, '?')} · {m.identity}" if m else key,
            "Status": r["status"],
            "Error": r.get("error") or "",
        })
```

- [ ] **Step 3: Check the file parses and tests still pass**

Run: `.venv\Scripts\python -c "import ast,pathlib; ast.parse(pathlib.Path('app.py').read_text(encoding='utf-8')); print('ok')"`
Then: `.venv\Scripts\python -m pytest tests -q`

Expected: `ok`, then all tests PASS

- [ ] **Step 4: Verify in the running app**

Reload `http://localhost:8501/?date=2026-08-02&days=3&auto=1` and confirm:
1. Each day has its own `Select all` / `Deselect all` pair, and pressing one ticks only that day's checkboxes.
2. With `Send mode` = `Preview only (no browser)`, select messages from two different days, press send, and confirm the results table shows a `Date` column distinguishing them.

Nothing is actually sent in Preview mode.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Select and review a whole day at a time

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Document the Saturday behaviour

**Files:**
- Modify: `README.md:88-105` (the "매일 오후 2시에 자동으로 띄우기" section)

**Interfaces:**
- Consumes: the finished behaviour from Tasks 1–4.
- Produces: nothing.

- [ ] **Step 1: Describe the Saturday window and the `days` parameter**

In `README.md`, after the line

```
한 번만 실행하면 Windows 작업 스케줄러에 등록됩니다. 매일 오후 2시에
**다음날 [TUT] 일정을 이미 검색한 상태로** 앱이 열립니다.
```

add:

```markdown
**토요일에는 3일치입니다.** 토요일 오후 2시 실행은 일요일·월요일·화요일 세션을
날짜별로 나누어 보여줍니다. 주말에 앉아서 다음 주 시작까지 한 번에 준비하라는
뜻입니다. 나머지 요일은 지금처럼 내일 하루만 다룹니다.

문자는 날짜별로 따로 만들어집니다. 같은 학생이 일요일과 화요일에 모두 수업이
있으면 문자 두 통이 각각 나가고, 각 문자에는 해당 날짜만 적힙니다.
```

- [ ] **Step 2: Document the `days` query parameter**

Replace this block:

```markdown
특정 날짜로 열고 싶으면 주소창에 직접 넣으셔도 됩니다:
`http://localhost:8501/?date=2026-08-01&auto=1`
```

with:

```markdown
특정 날짜로 열고 싶으면 주소창에 직접 넣으셔도 됩니다:

- 하루만: `http://localhost:8501/?date=2026-08-02&auto=1`
- 그 날부터 3일치: `http://localhost:8501/?date=2026-08-02&days=3&auto=1`

`days` 는 1~7 사이로 잘립니다. `date` 만 주면 그 하루만 봅니다.
화면의 **Days to cover** 칸으로도 같은 조정을 할 수 있습니다.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document the three-day Saturday window

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Done when

1. `.venv\Scripts\python -m pytest tests -q` is fully green.
2. A Saturday run with no query parameters covers Sunday, Monday and Tuesday; every other weekday covers tomorrow only.
3. One person appearing on two covered days produces two messages with independent draft boxes, checkboxes and result rows.
4. Each message's date line matches the day it was built for.
5. An empty day in the middle of the window does not hide the days around it.
6. `src/templates.py`, `src/calendar_service.py` and every `.bat` file are unchanged (`git diff --stat d8c497c..HEAD` lists none of them).
7. Nothing is sent without the user pressing the send button.
