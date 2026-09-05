"""Student names as the director writes them, for the teacher texts.

The calendar often carries a short form ("Daon", "Suhyun Byun") while the
Tutoring Daily Sheet's Students roster holds the full name the director uses
("Daon Yu", "Suhyun Sean Byun"). Teacher reminders print the roster spelling,
so the teacher's text and the director's records name the same student the
same way. Student and parent texts are not touched: they greet by Display
Name, which is a different choice made for a different reader.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from googleapiclient.discovery import build

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


def _words(name: str) -> set[str]:
    return set(_WORD_RE.findall(unicodedata.normalize("NFKC", name or "").casefold()))


@dataclass(frozen=True)
class CanonicalNames:
    names: tuple[str, ...] = ()

    def resolve(self, raw: str) -> str:
        """The roster spelling for a calendar name, or the name unchanged.

        An exact match (ignoring case and punctuation) wins. Otherwise the one
        roster name containing every word written is used, so "Daon" finds
        "Daon Yu" and "Suhyun Byun" finds "Suhyun Sean Byun". Two candidates
        ("Kim") or none ("Anthony") leave the calendar's spelling alone: a
        wrong full name in front of a teacher is worse than a short one.
        """
        raw = (raw or "").strip()
        want = _words(raw)
        if not want:
            return raw
        exact = [n for n in self.names if _words(n) == want]
        if len(exact) == 1:
            return exact[0]
        hits = [n for n in self.names if want <= _words(n)]
        return hits[0] if len(hits) == 1 else raw

    def resolve_all(self, raws: Iterable[str]) -> list[str]:
        return [self.resolve(r) for r in raws]


EMPTY = CanonicalNames()


def load_canonical_names(credentials, spreadsheet_id: str,
                         rng: str = "Students!A2:A") -> CanonicalNames:
    """Column A of the Students tab. Errors propagate; the app decides what to say."""
    if not spreadsheet_id:
        return EMPTY
    service = build("sheets", "v4", credentials=credentials)
    resp = (service.spreadsheets().values()
            .get(spreadsheetId=spreadsheet_id, range=rng).execute())
    names = tuple(str(r[0]).strip() for r in resp.get("values", [])
                  if r and str(r[0]).strip())
    return CanonicalNames(names)
