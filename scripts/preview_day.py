"""Gate-check CLI: print parsed [TUT] events for a date, no Streamlit needed.

Usage: python scripts/preview_day.py 2026-08-01
"""

import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.auth import get_credentials
from src.calendar_service import TutoringCalendarService

BOOTSTRAP_TOKEN = config.BASE_DIR / "token_sheet_bootstrap.json"


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    token = config.TOKEN_PATH if config.TOKEN_PATH.exists() else BOOTSTRAP_TOKEN
    scopes = config.SCOPES if token == config.TOKEN_PATH else None
    creds = get_credentials(str(config.CREDENTIALS_PATH), str(token),
                            scopes or ["https://www.googleapis.com/auth/calendar.readonly",
                                       "https://www.googleapis.com/auth/spreadsheets"])
    svc = TutoringCalendarService(creds, config.CALENDAR_ID, config.LOCAL_TZ)
    events, total = svc.list_tut_events_on(day)
    print(f"{day}: scanned {total} events, {len(events)} [TUT]")
    for e in events:
        p = e.parsed
        flag = "CANCELLED" if p.is_cancelled else "active"
        print(f"\n[{flag}] {e.start:%I:%M %p}-{e.end:%I:%M %p}  {e.raw_summary}")
        print(f"   teacher={p.teacher_name!r} students={p.student_names!r}")
        print(f"   subject={p.subject!r} clean={p.subject_clean!r} type={p.session_type!r}")
        if e.meet_link:
            print(f"   meet={e.meet_link}")
        if p.warnings:
            print(f"   warnings={p.warnings}")


if __name__ == "__main__":
    main()
