"""OAuth2 authentication for Google APIs."""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
    scopes: list[str] | None = None,
) -> Credentials:
    """Authenticate and return valid Google API credentials.

    Flow:
    1. Load existing token from token_path if available
    2. Refresh expired token if refresh_token exists
    3. Run browser-based OAuth flow if no valid token
    4. Save token for future use
    """
    scopes = scopes or DEFAULT_SCOPES
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                os.remove(token_path)
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds
