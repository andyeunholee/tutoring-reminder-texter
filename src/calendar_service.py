"""Single-day [TUT] event fetching from Google Calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from src.tut_parser import TUT_TAG_RE, TutEvent, build_tut_event

LOCAL_TZ = ZoneInfo("America/New_York")


class TutoringCalendarService:
    def __init__(self, credentials, calendar_id: str, tz: ZoneInfo = LOCAL_TZ):
        self.service = build("calendar", "v3", credentials=credentials)
        self.calendar_id = calendar_id
        self.tz = tz

    def list_events_on(self, day: date) -> list[dict]:
        """All raw events on the given local day (midnight to midnight, DST-safe)."""
        start = datetime.combine(day, time.min, tzinfo=self.tz)
        end = start + timedelta(days=1)
        events: list[dict] = []
        page_token = None
        while True:
            resp = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=start.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            events.extend(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return events

    def list_tut_events_on(self, day: date) -> tuple[list[TutEvent], int]:
        """Parsed [TUT] events on the day, plus total events scanned.

        The [TUT] filter is client-side: the API q= parameter tokenizes away
        bracket punctuation and is unreliable for a bracketed tag.
        """
        raw_events = self.list_events_on(day)
        tut_events: list[TutEvent] = []
        for raw in raw_events:
            if raw.get("status") == "cancelled":
                continue
            if not TUT_TAG_RE.search(raw.get("summary", "")):
                continue
            ev = build_tut_event(raw, self.tz)
            if ev is not None:
                tut_events.append(ev)
        return tut_events, len(raw_events)
