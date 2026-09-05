"""Central configuration: paths, constants, .env loading."""

import os
import shutil
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _ensure_local_ca_bundle() -> None:
    """Mirror certifi's CA bundle onto local disk and point TLS at the copy.

    OpenSSL cannot load a CA bundle that lives on the Google Drive virtual
    filesystem: every HTTPS handshake dies with SSLEOFError even though the
    bytes are identical to a working copy. Since this project lives under
    H:\\My Drive, the venv's certifi bundle is on that filesystem.
    """
    try:
        import certifi
    except ImportError:
        return
    src = Path(certifi.where())
    local_root = Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir())
    try:
        if src.is_relative_to(local_root):
            return
    except (AttributeError, ValueError):
        pass
    dst = local_root / "TutoringReminder" / "cacert.pem"
    try:
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    except OSError:
        return
    os.environ.setdefault("SSL_CERT_FILE", str(dst))
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(dst))


_ensure_local_ca_bundle()

# --- Google API auth ---
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token_tutoring.json"
# NOTE: if you ever change SCOPES, delete token_tutoring.json and re-consent.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# --- Calendar ---
CALENDAR_ID = os.getenv("CALENDAR_ID", "andy.lee@eliteprep.com")
LOCAL_TZ = ZoneInfo("America/New_York")

# --- Roster Google Sheet ---
ROSTER_SPREADSHEET_ID = os.getenv("ROSTER_SPREADSHEET_ID", "")
ROSTER_TEACHERS_RANGE = "Teachers!A2:F"   # F = Name in Student Texts
ROSTER_STUDENTS_RANGE = "Students!A2:H"   # H = Time Zone
ROSTER_ALIASES_RANGE = "Aliases!A2:C"

# --- Google Voice sender ---
# Keep the browser profile on a local disk: Google Drive's virtual filesystem
# corrupts Chrome profile locks, and Google blocks sign-in from the bundled
# Chromium ("This browser or app may not be secure"), so we drive real Chrome.
_LOCAL_ROOT = Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir()) / "TutoringReminder"
GV_USER_DATA_DIR = os.getenv("GV_USER_DATA_DIR", str(_LOCAL_ROOT / "gv_profile"))
# "chrome" = real installed Chrome (passes Google's sign-in check).
# Set to "" in .env to fall back to Playwright's bundled Chromium.
GV_BROWSER_CHANNEL = os.getenv("GV_BROWSER_CHANNEL", "chrome")
DELAY_BETWEEN_JOBS = float(os.getenv("DELAY_BETWEEN_JOBS", "4.0"))
SCREENSHOT_DIR = BASE_DIR / "debug_screenshots"

# --- Messaging ---
ORG_NAME = os.getenv("ORG_NAME", "Elite Prep")
DEFAULT_DRY_RUN = os.getenv("DEFAULT_DRY_RUN", "true").lower() in ("1", "true", "yes")
