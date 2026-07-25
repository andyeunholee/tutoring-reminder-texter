"""Interactive Google Voice login. Run this when sending says "Not logged in".

By default it logs into the profile configured as GV_USER_DATA_DIR (shared with
the other Google Voice automation), so signing in once fixes both projects.
Use --local to build a project-private profile instead.

    python sms/setup_gv_login.py
    python sms/setup_gv_login.py --local
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

import config  # noqa: E402
from sms.gv_sender import launch_gv_context  # noqa: E402

LOCAL_PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playwright_user_data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true",
                    help="use a project-private profile instead of the shared one")
    args = ap.parse_args()

    profile = LOCAL_PROFILE if args.local else config.GV_USER_DATA_DIR
    os.makedirs(profile, exist_ok=True)

    print(f"Profile: {profile}\n")
    print("A browser window will open at Google Voice.")
    print("1. Click 'Sign in' and log in with the Google account that owns your")
    print("   Google Voice number.")
    print("2. Wait until you can see your text message list.")
    print("3. CLOSE the browser window. This script then verifies the login.\n")

    logged_in = False
    with sync_playwright() as p:
        context = launch_gv_context(p, profile, channel=config.GV_BROWSER_CHANNEL, slow_mo=0)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://voice.google.com/messages")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            context.close()
        except Exception:
            pass

    # Re-open to confirm the session persisted.
    print("Verifying saved login...")
    with sync_playwright() as p:
        context = launch_gv_context(p, profile, channel=config.GV_BROWSER_CHANNEL, slow_mo=0)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://voice.google.com/messages")
        try:
            page.wait_for_selector('div[aria-label="Send new message"]', timeout=20000)
            logged_in = True
        except Exception:
            logged_in = False
        try:
            context.close()
        except Exception:
            pass

    if logged_in:
        print("\nSUCCESS: Google Voice login saved. You can send messages now.")
    else:
        print(f"\nNOT LOGGED IN yet (landed without a compose button).")
        print("Run this script again and make sure you reach the message list "
              "before closing the window.")
    if args.local:
        print(f"\nAlso add this line to .env:\n   GV_USER_DATA_DIR={profile}")


if __name__ == "__main__":
    main()
