"""OAuth2 authentication for Google APIs."""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def _covers(granted: list[str], wanted: list[str]) -> bool:
    """True when the granted scopes already permit everything wanted.

    A write scope implies its read-only form: a token holding
    ".../auth/spreadsheets" can obviously satisfy a request for
    ".../auth/spreadsheets.readonly". Without this, a perfectly usable token
    is thrown away and the user is dragged through the consent screen again.
    """
    have = set(granted)
    for scope in wanted:
        if scope in have:
            continue
        if scope.endswith(".readonly") and scope[: -len(".readonly")] in have:
            continue
        return False
    return True


def _load_token(token_path: str, scopes: list[str]) -> Credentials | None:
    """Load a stored token, keeping it if its scopes cover what we need."""
    try:
        with open(token_path, encoding="utf-8") as f:
            granted = json.load(f).get("scopes") or []
    except (OSError, ValueError):
        return None
    if not _covers(granted, scopes):
        return None
    # Hand google-auth the scopes actually on the token, so it does not
    # consider the credentials mis-scoped.
    return Credentials.from_authorized_user_file(token_path, granted)


def get_credentials(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
    scopes: list[str] | None = None,
) -> Credentials:
    """Authenticate and return valid Google API credentials.

    Flow:
    1. Reuse the stored token when its scopes cover what is requested
    2. Refresh it if expired
    3. Otherwise run the browser consent flow and store the result
    """
    scopes = scopes or DEFAULT_SCOPES
    creds = _load_token(token_path, scopes) if os.path.exists(token_path) else None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(
                port=0,
                authorization_prompt_message=(
                    "Sign in with your PERSONAL Google account "
                    "(andyeunholee@gmail.com), not the eliteprep.com work account "
                    "- the work account is blocked by its Workspace admin.\n"
                    "Opening the browser..."
                ),
            )

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds
