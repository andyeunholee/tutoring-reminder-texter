"""Google Voice sender: one browser session, many send jobs.

Combines the proven techniques of the two existing codebases:
- 1:1 sends navigate straight to the conversation URL and verify delivery
  (from cursor/MyProject/Google_Voice_Text_Automation/bulk_send.py).
- Group sends use the new-message + comma-chip recipient flow
  (from AntiGravity/calendar-appt-confirmation/sms_code/bulk_send.py).

Job dict: {"id": str, "label": str, "recipients": [str], "group_mode": bool,
           "message": str}
"""

from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

MESSAGES_URL = "https://voice.google.com/messages"

# Google refuses sign-in from an obviously automated browser
# ("This browser or app may not be secure"). Launching real Chrome and dropping
# the automation banner/flag is what makes the login stick.
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-default-browser-check",
    "--no-first-run",
]
IGNORED_DEFAULT_ARGS = ["--enable-automation"]


class ProfileInUseError(RuntimeError):
    """The browser profile is already open in another window."""


def _profile_in_use(err: str) -> bool:
    return ("Opening in existing browser session" in err
            or "ProcessSingleton" in err
            or "already in use" in err)


def launch_gv_context(p, user_data_dir, *, channel="chrome", headless=False, slow_mo=50):
    """Launch a persistent browser context for Google Voice.

    Falls back to bundled Chromium ONLY when the requested channel is not
    installed. Any other failure is raised: silently dropping to Chromium
    would reintroduce Google's "this browser may not be secure" block.
    """
    kwargs = dict(
        user_data_dir=user_data_dir,
        headless=headless,
        slow_mo=slow_mo,
        args=STEALTH_ARGS,
        ignore_default_args=IGNORED_DEFAULT_ARGS,
    )
    if channel:
        try:
            return p.chromium.launch_persistent_context(channel=channel, **kwargs)
        except Exception as e:
            err = str(e)
            if _profile_in_use(err):
                raise ProfileInUseError(err) from e
            if "executable doesn't exist" not in err.lower() and "not found" not in err.lower():
                raise
            # channel genuinely missing -> bundled Chromium is the only option
    try:
        return p.chromium.launch_persistent_context(**kwargs)
    except Exception as e:
        if _profile_in_use(str(e)):
            raise ProfileInUseError(str(e)) from e
        raise

MESSAGE_BOX_SELECTORS = [
    'textarea[aria-label="Type a message"]',
    'div[contenteditable="true"][aria-label="Type a message"]',
    'textarea[placeholder="Type a message"]',
]
SEND_BTN_SELECTORS = [
    'div[role="button"][aria-label="Send message"]',
    'button[aria-label="Send message"]',
    'div[aria-label="Send message"]',
]
NEW_MSG_SELECTORS = [
    'div[aria-label="Send new message"]',
    'div[role="button"][aria-label="Send new message"]',
]
RECIPIENT_INPUT_SELECTORS = [
    'input[placeholder="Type a name or phone number"]',
    'input[aria-label="Type a name or phone number"]',
    'input[placeholder="Add recipients"]',
    'input[aria-label="Add recipients"]',
    'div[role="combobox"] input',
]


def normalize_phone_number(raw_input) -> str:
    try:
        s = str(raw_input).strip()
        if "E" in s.upper() or "." in s:
            try:
                s = str(int(float(s)))
            except ValueError:
                pass
        return "".join(filter(str.isdigit, s))
    except Exception:
        return ""


def _conversation_url(number: str) -> str:
    digits = normalize_phone_number(number)
    if len(digits) == 10:
        return f"https://voice.google.com/u/0/messages?itemId=t.%2B1{digits}"
    return f"https://voice.google.com/u/0/messages?itemId=t.%2B{digits}"


def _screenshot(page, screenshot_dir, name):
    if not screenshot_dir:
        return
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        page.screenshot(path=os.path.join(screenshot_dir, f"{name}.png"))
    except Exception:
        pass


def _is_logged_in(page) -> bool:
    """True only when the real Messages UI is present.

    A logged-out session does NOT land on a signin URL — Google Voice quietly
    redirects to its marketing page, which has no compose button. Checking the
    URL alone reports a confusing "message box not found" later, so require a
    positive signal instead.
    """
    url = page.url
    for marker in ("signin", "AccountChooser", "accounts.google.com",
                   "workspace.google.com", "/about"):
        if marker in url:
            return False
    for sel in NEW_MSG_SELECTORS + ['div[gv-test-id="thread-list"]', "gv-thread-list"]:
        try:
            page.wait_for_selector(sel, timeout=8000)
            return True
        except Exception:
            continue
    return False


def _find_message_box(page) -> str | None:
    for sel in MESSAGE_BOX_SELECTORS:
        try:
            if page.is_visible(sel):
                return sel
        except Exception:
            continue
    return None


def _read_box(page, sel) -> str:
    try:
        return page.input_value(sel)
    except Exception:
        try:
            return page.inner_text(sel)
        except Exception:
            return ""


def _element_has_focus(page, sel) -> bool:
    """True when `sel` is the element that will receive the next keystroke."""
    try:
        handle = page.locator(sel).first.element_handle()
        return bool(page.evaluate("(el) => el === document.activeElement", handle))
    except Exception:
        return False


def _focus_message_box(page, sel, log) -> bool:
    """Put focus in the message box and prove it took. False if it never did.

    Clicking is not enough on the compose screen. Two contact-autocomplete
    inputs float over the conversation there — the compose "Add recipients"
    box and the dialpad's "Enter a name or number" box — and either can swallow
    the click or pull focus straight back. Keystrokes then land in a contact
    search while the message box stays empty, which is how a whole reminder
    once ended up typed into a contact lookup instead of being sent.
    """
    for attempt in range(3):
        if attempt == 2:
            # Last resort: close whatever dropdown is holding on to focus.
            try:
                page.keyboard.press("Escape")
                time.sleep(0.3)
            except Exception:
                pass
        try:
            page.click(sel, timeout=5000)
        except Exception as e:
            log(f"Message box click failed (attempt {attempt + 1}): {e}")
        time.sleep(0.3)
        if _element_has_focus(page, sel):
            return True
        # A click goes to whatever covers the coordinates; a direct DOM focus()
        # cannot be intercepted that way.
        try:
            page.focus(sel)
        except Exception:
            pass
        try:
            page.evaluate("(el) => el.focus()",
                          page.locator(sel).first.element_handle())
        except Exception:
            pass
        time.sleep(0.3)
        if _element_has_focus(page, sel):
            return True
        log(f"Focus did not land in the message box (attempt {attempt + 1})")
    return False


def _type_multiline(page, sel, text, log):
    """Type into the box using Shift+Enter for line breaks (Enter would send)."""
    if not _focus_message_box(page, sel, log):
        # Bail before a single keystroke: typing here would go into a contact
        # search field, and the Control+A below would clear whatever it owns.
        raise RuntimeError(
            "could not put focus in the message box — a contact autocomplete is "
            "probably covering it; nothing was typed")
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    time.sleep(0.2)
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        if line:
            page.keyboard.type(line)
        if idx < len(lines) - 1:
            page.keyboard.press("Shift+Enter")
            time.sleep(0.05)
    time.sleep(0.5)
    content = _read_box(page, sel)
    if not content.strip():
        raise RuntimeError("message box empty after typing")
    # nudge frameworks that gate the Send button on an input event
    try:
        page.evaluate(
            "(el) => el.dispatchEvent(new Event('input', { bubbles: true }))",
            page.locator(sel).first.element_handle(),
        )
    except Exception:
        pass
    time.sleep(0.3)


def _press_send(page, sel, log) -> None:
    for btn in SEND_BTN_SELECTORS:
        try:
            if page.is_visible(btn):
                page.click(btn)
                time.sleep(2)
                return
        except Exception:
            continue
    log("Send button not found; falling back to Enter key")
    page.focus(sel)
    time.sleep(0.3)
    page.keyboard.press("Enter")
    time.sleep(2)


def _verify_sent(page, sel) -> bool:
    return not _read_box(page, sel).strip()


def _focus_hunter(page, log) -> str | None:
    """Tab until the message textarea has focus (new-message compose screen)."""
    for _ in range(8):
        try:
            if page.evaluate("document.activeElement.tagName === 'TEXTAREA'"):
                break
            if page.evaluate("document.activeElement.getAttribute('aria-label')") == "Type a message":
                break
        except Exception:
            pass
        page.keyboard.press("Tab")
        time.sleep(0.4)
    sel = _find_message_box(page)
    if sel is None:
        log("Warning: could not locate message box after focus hunt")
    return sel


def _open_new_message(page, recipients, log, *, group_mode) -> bool:
    """Start a compose via the 'Send new message' button and add recipients.

    group_mode=True uses the comma-chip trick for multiple numbers;
    group_mode=False selects the single number via ArrowDown+Enter
    (needed for numbers with no existing conversation thread, where the
    direct conversation URL shows no message box).
    """
    page.goto(MESSAGES_URL)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    time.sleep(2)

    clicked = False
    for _ in range(3):
        for sel in NEW_MSG_SELECTORS:
            try:
                if page.is_visible(sel):
                    page.click(sel, timeout=2000)
                    clicked = True
                    break
            except Exception:
                continue
        if clicked:
            break
        time.sleep(1)
    if not clicked:
        log("Could not find 'Send new message' button")
        return False

    try:
        page.wait_for_selector(RECIPIENT_INPUT_SELECTORS[0], state="visible", timeout=8000)
    except Exception:
        pass

    for raw in recipients:
        number = normalize_phone_number(raw)
        if not number:
            continue
        log(f"Adding recipient {number}")
        active = None
        for sel in RECIPIENT_INPUT_SELECTORS:
            try:
                for el in page.query_selector_all(sel):
                    if not el.is_visible():
                        continue
                    aria = el.get_attribute("aria-label") or ""
                    ph = el.get_attribute("placeholder") or ""
                    if "Search" in aria or "Search" in ph:
                        continue
                    active = sel
                    break
            except Exception:
                continue
            if active:
                break
        if not active:
            active = RECIPIENT_INPUT_SELECTORS[0]
        try:
            page.click(active)
        except Exception:
            pass
        page.keyboard.type(number, delay=50)
        time.sleep(1.0)
        if group_mode:
            page.keyboard.type(",")   # comma turns the number into a chip
            time.sleep(1.0)
        else:
            # Single recipient: pick the autocomplete entry. A brand-new number
            # has no contact/thread, so GV offers a "Send to <number>" row that
            # only ArrowDown+Enter selects.
            page.keyboard.press("ArrowDown")
            time.sleep(0.5)
            page.keyboard.press("Enter")
            time.sleep(1.5)
    return True


def _read_recipient_chips(page) -> list[str]:
    """Digits of every recipient chip currently on the compose screen.

    Google Voice labels each chip's remove button "Remove 4 7 0 5 5 5 0 1 2 4?",
    so the digits are recoverable from the aria-label.
    """
    seen, out = set(), []
    try:
        for el in page.query_selector_all('[aria-label*="Remove"]'):
            label = el.get_attribute("aria-label") or ""
            digits = "".join(ch for ch in label if ch.isdigit())
            if len(digits) >= 10 and digits not in seen:
                seen.add(digits)
                out.append(digits)
    except Exception:
        pass
    return out


def _verify_recipients(page, expected, log) -> str | None:
    """Return an error string when the composed recipients differ from expected.

    This is the guard against texting the wrong family: if the chips on screen
    do not match exactly what we intended, refuse to send.
    """
    want = {n[-10:] for n in expected if n}
    chips = _read_recipient_chips(page)
    got = {c[-10:] for c in chips}
    if not chips:
        return "no recipient chips found on the compose screen"
    if got != want:
        return (f"recipient mismatch — intended {sorted(want)}, "
                f"compose screen shows {sorted(got)}")
    log(f"Recipients verified: {', '.join(sorted(got))}")
    return None


def _send_one(page, job, log, *, dry_run=False, screenshot_dir=None) -> dict:
    recipients = [normalize_phone_number(r) for r in job["recipients"]]
    recipients = [r for r in recipients if r]
    if not recipients:
        return {"status": "failed", "error": "no valid recipients"}
    message = job["message"]
    label = job.get("label", job.get("id", "job"))
    group = job.get("group_mode", False) and len(recipients) > 1

    composed_new = False
    if group:
        if not _open_new_message(page, recipients, log, group_mode=True):
            _screenshot(page, screenshot_dir, f"{job['id']}_no_new_msg_btn")
            return {"status": "failed", "error": "could not open new group message"}
        composed_new = True
        sel = _focus_hunter(page, log)
    else:
        # Fast path: jump straight into an existing conversation thread.
        log(f"Opening conversation with {recipients[0]}")
        page.goto(_conversation_url(recipients[0]))
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        time.sleep(4)
        sel = _find_message_box(page)
        if sel is not None:
            # Confirm the URL still points at the thread we asked for; a
            # redirect would mean we are typing into someone else's thread.
            if normalize_phone_number(recipients[0])[-10:] not in \
                    normalize_phone_number(page.url)[-40:]:
                _screenshot(page, screenshot_dir, f"{job['id']}_wrong_thread")
                return {"status": "failed",
                        "error": f"opened the wrong conversation ({page.url})"}
        else:
            # No thread with this number yet -> the direct URL renders no
            # message box. Compose it as a new message instead.
            log("No existing conversation; composing a new message instead")
            if not _open_new_message(page, recipients, log, group_mode=False):
                _screenshot(page, screenshot_dir, f"{job['id']}_no_new_msg_btn")
                return {"status": "failed", "error": "could not open new message"}
            composed_new = True
            sel = _focus_hunter(page, log)

    if sel is None:
        _screenshot(page, screenshot_dir, f"{job['id']}_no_message_box")
        return {"status": "failed", "error": "message box not found"}

    if composed_new:
        problem = _verify_recipients(page, recipients, log)
        if problem:
            _screenshot(page, screenshot_dir, f"{job['id']}_recipient_mismatch")
            return {"status": "failed", "error": problem}

    try:
        _type_multiline(page, sel, message, log)
    except Exception as e:
        _screenshot(page, screenshot_dir, f"{job['id']}_typing_failed")
        return {"status": "failed", "error": f"typing failed: {e}"}

    if dry_run:
        _screenshot(page, screenshot_dir, f"dry_{job['id']}")
        log(f"[DRY RUN] Composed but NOT sent: {label}")
        page.goto(MESSAGES_URL)  # discard the draft
        time.sleep(1.5)
        return {"status": "dry_run", "error": None}

    _press_send(page, sel, log)

    if _verify_sent(page, sel):
        log(f"Sent: {label}")
        return {"status": "sent", "error": None}

    # last resort: Tab + Enter (from the older codebase)
    page.focus(sel)
    time.sleep(0.4)
    page.keyboard.press("Tab")
    time.sleep(0.4)
    page.keyboard.press("Enter")
    time.sleep(2)
    if _verify_sent(page, sel):
        log(f"Sent (fallback): {label}")
        return {"status": "sent", "error": None}

    _screenshot(page, screenshot_dir, f"{job['id']}_send_failed")
    return {"status": "failed", "error": "text still in input box after send attempts"}


def run_jobs(jobs, progress_callback=None, *, dry_run=False, user_data_dir=None,
             delay_between=4.0, screenshot_dir=None, browser_channel="chrome",
             on_job_start=None, on_job_result=None) -> list[dict]:
    def log(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    results = [{"id": j["id"], "status": "skipped", "error": None} for j in jobs]
    if not jobs:
        return results

    mode = "DRY RUN" if dry_run else "LIVE"
    log(f"Starting {mode} run: {len(jobs)} message(s)")

    with sync_playwright() as p:
        try:
            context = launch_gv_context(p, user_data_dir, channel=browser_channel)
        except ProfileInUseError:
            log("CRITICAL: The automation browser window is still open. "
                "Close every Chrome window that this tool opened, then retry.")
            return results
        except Exception as e:
            log(f"CRITICAL: Could not launch browser: {e}")
            return results

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(MESSAGES_URL)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            time.sleep(2)

            if not _is_logged_in(page):
                _screenshot(page, screenshot_dir, "not_logged_in")
                log("CRITICAL: Not logged in to Google Voice (landed on "
                    f"{page.url}). No messages were attempted.")
                log("FIX: run  login_google_voice.bat  and sign in, then retry.")
                return results

            for i, job in enumerate(jobs):
                if on_job_start:
                    on_job_start(i, job)
                try:
                    results[i] = {"id": job["id"], **_send_one(
                        page, job, log, dry_run=dry_run, screenshot_dir=screenshot_dir)}
                except Exception as e:
                    err = str(e)
                    closed = ("TargetClosed" in type(e).__name__
                              or "has been closed" in err or "Connection closed" in err)
                    if closed:
                        log("CRITICAL: Browser was closed. Remaining messages skipped.")
                        results[i] = {"id": job["id"], "status": "skipped",
                                      "error": "browser closed"}
                        break
                    results[i] = {"id": job["id"], "status": "failed", "error": err}
                    log(f"Error on {job.get('label', job['id'])}: {err}")
                if on_job_result:
                    on_job_result(i, job, results[i])
                if i < len(jobs) - 1:
                    time.sleep(delay_between)
        finally:
            try:
                context.close()
            except Exception:
                pass
            log("Browser session closed.")
    return results
