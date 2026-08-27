"""One-time script: create the roster Google Sheet and seed names from the calendar.

Usage:
    python scripts/create_roster_sheet.py [--seed-days 30]

Uses a SEPARATE token (token_sheet_bootstrap.json) with spreadsheet write scope,
so the main app token stays read-only. Prints the new spreadsheet ID + URL;
paste the ID into .env as ROSTER_SPREADSHEET_ID, then fill in phone numbers.
"""

import argparse
import os
import sys
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from googleapiclient.discovery import build

import config
from src.auth import get_credentials
from src.calendar_service import TutoringCalendarService

BOOTSTRAP_TOKEN = str(config.BASE_DIR / "token_sheet_bootstrap.json")
BOOTSTRAP_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

TEACHER_HEADERS = ["Teacher Name (as in calendar)", "Display Name", "Phone", "Active", "Notes",
                   "Full Name (in student texts)"]
STUDENT_HEADERS = ["Student Name (as in calendar)", "Display Name", "Student Phone",
                   "Parent Name", "Parent Phone", "Active", "Notes", "Time Zone"]
ALIAS_HEADERS = ["Name As Written In Calendar", "Type (teacher/student)",
                 "Canonical Name (must match col A of Teachers/Students)"]


def collect_names(creds, days: int) -> tuple[list[str], list[str]]:
    from datetime import datetime, time

    from src.tut_parser import TUT_TAG_RE, parse_tut_title

    past_days, future_days = days
    svc = TutoringCalendarService(creds, config.CALENDAR_ID, config.LOCAL_TZ)
    start = datetime.combine(date.today() - timedelta(days=past_days), time.min,
                             tzinfo=config.LOCAL_TZ)
    end = datetime.combine(date.today() + timedelta(days=future_days + 1), time.min,
                           tzinfo=config.LOCAL_TZ)
    teachers, students = {}, {}
    page_token = None
    while True:
        resp = svc.service.events().list(
            calendarId=config.CALENDAR_ID,
            timeMin=start.isoformat(), timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime", maxResults=250,
            pageToken=page_token,
        ).execute()
        for raw in resp.get("items", []):
            summary = raw.get("summary", "")
            if not TUT_TAG_RE.search(summary):
                continue
            p = parse_tut_title(summary)
            if p.teacher_name:
                teachers.setdefault(p.teacher_name.casefold(), p.teacher_name)
            for s in p.student_names:
                students.setdefault(s.casefold(), s)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return sorted(teachers.values()), sorted(students.values())


def create_sheet(sheets, teachers, students):
    body = {
        "properties": {"title": "Tutoring Reminder Roster"},
        "sheets": [
            {"properties": {"title": "Teachers", "gridProperties": {"frozenRowCount": 1}}},
            {"properties": {"title": "Students", "gridProperties": {"frozenRowCount": 1}}},
            {"properties": {"title": "Aliases", "gridProperties": {"frozenRowCount": 1}}},
        ],
    }
    ss = sheets.spreadsheets().create(body=body).execute()
    ssid = ss["spreadsheetId"]
    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=ssid,
        body={"valueInputOption": "RAW", "data": [
            {"range": "Teachers!A1",
             "values": [TEACHER_HEADERS] + [[t, t, "", "TRUE", "", ""] for t in teachers]},
            {"range": "Students!A1",
             "values": [STUDENT_HEADERS] + [[s, "", "", "", "", "TRUE", "", ""] for s in students]},
            {"range": "Aliases!A1", "values": [ALIAS_HEADERS]},
        ]},
    ).execute()
    print("\n=== Roster spreadsheet created ===")
    print(f"URL: {ss['spreadsheetUrl']}")
    print(f"ID:  {ssid}")
    print("\nNext steps:")
    print(f"1. Put this line in .env:\n   ROSTER_SPREADSHEET_ID={ssid}")
    print("2. Open the sheet and fill in phone numbers (and parent names).")


def sync_sheet(sheets, ssid, teachers, students):
    """Append names that aren't in the sheet yet. Never touches existing rows."""
    from src.roster import norm_key

    resp = sheets.spreadsheets().values().batchGet(
        spreadsheetId=ssid, ranges=["Teachers!A2:A", "Students!A2:A"]).execute()
    ranges = resp.get("valueRanges", [])

    def existing(i, is_teacher):
        vals = ranges[i].get("values", []) if i < len(ranges) else []
        return {norm_key(r[0], is_teacher=is_teacher) for r in vals if r and r[0].strip()}

    have_t = existing(0, True)
    have_s = existing(1, False)
    new_t = [t for t in teachers if norm_key(t, is_teacher=True) not in have_t]
    new_s = [s for s in students if norm_key(s) not in have_s]

    if not new_t and not new_s:
        print("\nRoster already has every name found on the calendar. Nothing to add.")
        return

    if new_t:
        sheets.spreadsheets().values().append(
            spreadsheetId=ssid, range="Teachers!A1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [[t, t, "", "TRUE", ""] for t in new_t]},
        ).execute()
    if new_s:
        sheets.spreadsheets().values().append(
            spreadsheetId=ssid, range="Students!A1",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [[s, "", "", "", "", "TRUE", ""] for s in new_s]},
        ).execute()

    print(f"\n=== Added {len(new_t)} teacher(s), {len(new_s)} student(s) ===")
    for t in new_t:
        print(f"  teacher: {t}")
    for s in new_s:
        print(f"  student: {s}")
    print(f"\nhttps://docs.google.com/spreadsheets/d/{ssid}/edit")
    print("Fill in the phone numbers for the new rows.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-days", type=int, default=30,
                    help="how many days BACK to scan for names")
    ap.add_argument("--future-days", type=int, default=90,
                    help="how many days FORWARD to scan for names")
    ap.add_argument("--new", action="store_true",
                    help="force creating a new sheet even if ROSTER_SPREADSHEET_ID is set")
    args = ap.parse_args()

    print("Authenticating (browser may open for consent)...")
    creds = get_credentials(str(config.CREDENTIALS_PATH), BOOTSTRAP_TOKEN, BOOTSTRAP_SCOPES)

    print(f"Scanning [TUT] events from {args.seed_days} days back "
          f"to {args.future_days} days ahead...")
    teachers, students = collect_names(creds, (args.seed_days, args.future_days))
    print(f"  found {len(teachers)} teachers, {len(students)} students")

    sheets = build("sheets", "v4", credentials=creds)
    ssid = config.ROSTER_SPREADSHEET_ID
    if ssid and not args.new:
        print(f"Syncing existing roster {ssid} ...")
        sync_sheet(sheets, ssid, teachers, students)
    else:
        create_sheet(sheets, teachers, students)


if __name__ == "__main__":
    main()
