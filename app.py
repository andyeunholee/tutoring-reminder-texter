"""Tutoring Reminder Texter — Streamlit UI.

Orchestration only: parsing lives in src/tut_parser.py, roster in src/roster.py,
message building in src/message_builder.py, sending in sms/.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date

import streamlit as st

import config
from src.auth import get_credentials
from src.calendar_service import TutoringCalendarService
from src.coverage_window import coverage_days, resolve_window
from src.message_builder import build_messages
from src.roster import RosterUnavailable, load_roster
from sms.gv_sender import normalize_phone_number

st.set_page_config(page_title="Tutoring Reminder Texter", page_icon="📅", layout="wide")

RUNNER = str(config.BASE_DIR / "sms" / "sms_job_runner.py")


def parse_redirect(text: str) -> tuple[list[str], list[str]]:
    """Split the test-redirect box into usable numbers, and unusable leftovers.

    Without this, "714-300-3245, 470-555-0100" is stripped to digits as a single
    string and becomes one 20-digit number that quietly goes nowhere.
    """
    good, bad = [], []
    for part in re.split(r"[,;/\n]+| {2,}", text or ""):
        part = part.strip()
        if not part:
            continue
        digits = normalize_phone_number(part)
        if not 10 <= len(digits) <= 11:
            bad.append(part)
        elif digits not in good:          # a repeat is harmless, just ignore it
            good.append(digits)
    return good, bad


# ---------- cached resources ----------

@st.cache_resource(show_spinner="Authenticating with Google...")
def google_creds():
    return get_credentials(str(config.CREDENTIALS_PATH), str(config.TOKEN_PATH), config.SCOPES)


@st.cache_data(ttl=300, show_spinner="Loading roster from Google Sheets...")
def cached_roster(spreadsheet_id: str):
    return load_roster(
        google_creds(),
        spreadsheet_id,
        {
            "teachers": config.ROSTER_TEACHERS_RANGE,
            "students": config.ROSTER_STUDENTS_RANGE,
            "aliases": config.ROSTER_ALIASES_RANGE,
        },
    )


# ---------- session state ----------

ss = st.session_state
# day_results: list of {"day": date, "events": [...], "total_scanned": int}
# None means "no search has been run yet".
ss.setdefault("day_results", None)
ss.setdefault("messages", [])
ss.setdefault("results", {})       # key -> {"status": ..., "error": ...}
ss.setdefault("run_log", [])
ss.setdefault("autosearch_done", False)


# ---------- sidebar ----------

with st.sidebar:
    st.header("Settings")

    spreadsheet_id = st.text_input(
        "Roster spreadsheet ID",
        value=config.ROSTER_SPREADSHEET_ID,
        help="From .env ROSTER_SPREADSHEET_ID. Run scripts/create_roster_sheet.py to create one.",
    )
    if st.button("Reload roster"):
        cached_roster.clear()
        st.rerun()

    dry_mode = st.radio(
        "Send mode",
        ["Preview only (no browser)", "Browser rehearsal (no send)", "LIVE SEND"],
        index=0 if config.DEFAULT_DRY_RUN else 2,
        help="Preview: show what would be sent. Rehearsal: browser composes each "
             "message and screenshots it but never presses send. LIVE: real texts.",
    )

    redirect_raw = st.text_input(
        "Redirect ALL messages to these numbers (test)",
        value="",
        help="If set, every message goes ONLY to these numbers instead of the real "
             "recipients. Separate several with commas — give two or more and they "
             "are texted as one group, so you can test group messages on your own phones.",
    )
    redirect_to, redirect_bad = parse_redirect(redirect_raw)
    if redirect_bad:
        st.error("Not a usable phone number: " + ", ".join(redirect_bad))
    elif redirect_to:
        st.warning(
            f"All messages will go to {', '.join(redirect_to)} — "
            + ("as ONE group text." if len(redirect_to) > 1 else "1:1.")
        )

    st.divider()
    merge_toggle = st.toggle("Merge same-day sessions into one message", value=True)
    include_cancelled = st.toggle("Include cancelled events", value=False)
    send_teachers = st.toggle("Teacher messages", value=True)
    send_students = st.toggle("Student + parent messages", value=True)

    st.divider()
    st.caption(f"Calendar: `{config.CALENDAR_ID}`")
    st.caption(f"GV profile: `{config.GV_USER_DATA_DIR}`")


# ---------- screen 1: date + search ----------

st.title("📅 Tutoring Reminder Texter")

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

# rebuild messages every run so sidebar toggles apply (drafts survive via setdefault)
try:
    roster = cached_roster(spreadsheet_id)
except RosterUnavailable as e:
    st.error(str(e))
    if st.button("Try again"):
        cached_roster.clear()
        st.rerun()
    st.stop()
except Exception as e:
    st.error(f"Roster load failed: {e}")
    st.stop()

if roster.load_errors:
    st.warning("Roster issues: " + "; ".join(roster.load_errors))

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

# draft/checkbox state: setdefault so edits survive reruns; prune stale keys
valid_keys = {m.key for m in messages}
for m in messages:
    ss.setdefault(f"draft_{m.key}", m.body)
    ss.setdefault(f"send_{m.key}", not m.blocked and not m.is_cancelled)
for k in list(ss.keys()):
    if (k.startswith("draft_") or k.startswith("send_")) and k.split("_", 1)[1] not in valid_keys:
        del ss[k]


# ---------- screen 2: events summary ----------

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


# ---------- screen 3: review list ----------

st.divider()
st.subheader("✉️ Review messages")

blocked = [m for m in messages if m.blocked]
if blocked:
    st.error(
        f"{len(blocked)} of {len(messages)} message(s) cannot be sent — "
        "missing roster entries or phone numbers. See the red rows below."
    )
if redirect_to:
    st.warning(f"⚠️ TEST MODE: every message will be redirected to {redirect_to}")

if not messages:
    st.info("Nothing to send for these dates with the current toggles.")
    st.stop()

KIND_LABEL = {"teacher": "👨‍🏫 TEACHER", "student_group": "👨‍👩‍👧 STUDENT+PARENT"}

c1, c2, c3 = st.columns(3)
if c1.button("Select all"):
    for m in messages:
        if not m.blocked:
            ss[f"send_{m.key}"] = True
if c2.button("Deselect all"):
    for m in messages:
        ss[f"send_{m.key}"] = False
if c3.button("Reset drafts to templates"):
    for m in messages:
        ss[f"draft_{m.key}"] = m.body

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

# ---------- screen 4: send ----------

def build_jobs(selected):
    jobs = []
    for m in selected:
        recipients = m.phones
        group = m.group_mode
        if redirect_to:
            recipients = list(redirect_to)
            group = len(redirect_to) > 1
        jobs.append({
            "id": m.key,
            "label": f"{m.kind} · {m.identity}",
            "recipients": recipients,
            "group_mode": group,
            "message": ss[f"draft_{m.key}"],
        })
    return jobs


def run_send(jobs):
    dry_run = dry_mode != "LIVE SEND"
    payload = {
        "dry_run": dry_run,
        "user_data_dir": config.GV_USER_DATA_DIR,
        "delay_between_jobs": config.DELAY_BETWEEN_JOBS,
        "screenshot_dir": str(config.SCREENSHOT_DIR),
        "browser_channel": config.GV_BROWSER_CHANNEL,
        "jobs": jobs,
    }
    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    label_by_id = {j["id"]: j["label"] for j in jobs}
    try:
        with st.status("Sending messages…", expanded=True) as status:
            progress_bar = st.progress(0.0)
            log_box = st.empty()
            proc = subprocess.Popen(
                [sys.executable, RUNNER, tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(config.BASE_DIR),
            )
            done_summary = None
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                if line.startswith("PROGRESS:"):
                    ss.run_log.append(line[9:])
                elif line.startswith("JOBSTART:"):
                    info = json.loads(line[9:])
                    progress_bar.progress(
                        (info["index"] - 1) / max(info["total"], 1),
                        text=f"{info['index']}/{info['total']} — "
                             f"{label_by_id.get(info['id'], info['id'])}",
                    )
                elif line.startswith("JOBRESULT:"):
                    r = json.loads(line[10:])
                    ss.results[r["id"]] = r
                elif line.startswith("DONE:"):
                    done_summary = json.loads(line[5:])
                elif line.startswith("ERROR_TRACE:"):
                    ss.run_log.append(line)
                else:
                    ss.run_log.append(line)
                log_box.code("\n".join(ss.run_log[-25:]))
            progress_bar.progress(1.0)
            if done_summary:
                status.update(
                    label=f"Done — sent {done_summary.get('sent', 0)}, "
                          f"dry-run {done_summary.get('dry_run', 0)}, "
                          f"failed {done_summary.get('failed', 0)}, "
                          f"skipped {done_summary.get('skipped', 0)}",
                    state="complete",
                )
            else:
                status.update(label="Subprocess ended without a DONE summary — check the log.",
                              state="error")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


if submitted:
    selected = [m for m in messages
                if not m.blocked and ss.get(f"send_{m.key}", False)]
    if not selected:
        st.warning("No messages selected.")
    elif dry_mode == "Preview only (no browser)":
        st.subheader("Preview (nothing sent)")
        jobs = build_jobs(selected)
        for j in jobs:
            with st.container(border=True):
                st.markdown(f"**{j['label']}** → {', '.join(j['recipients'])}"
                            + (" (group)" if j["group_mode"] else " (1:1)"))
                st.code(j["message"])
        with st.expander("Raw job JSON"):
            st.json(jobs)
        for j in jobs:
            ss.results[j["id"]] = {"id": j["id"], "status": "preview", "error": None}
    else:
        run_send(build_jobs(selected))


# ---------- results + retry ----------

if ss.results:
    st.divider()
    st.subheader("Results")
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
    st.dataframe(res_rows, use_container_width=True, hide_index=True)

    failed_keys = [k for k, r in ss.results.items()
                   if r["status"] in ("failed", "skipped") and k in by_key]
    if failed_keys and dry_mode == "LIVE SEND":
        if st.button(f"🔁 Retry {len(failed_keys)} failed/skipped only"):
            retry = [by_key[k] for k in failed_keys if not by_key[k].blocked]
            run_send(build_jobs(retry))
            st.rerun()
