"""The message body must never be typed into a contact-search field.

Google Voice's compose screen floats two autocomplete text inputs over the
conversation: the compose "Add recipients" box and the dialpad's "Enter a name
or number" box. Playwright types into whatever holds DOM focus, so if focus sits
on one of those, the whole reminder goes into a contact search instead of the
message box.
"""

import pytest

from sms.gv_sender import _type_multiline

MSG_SEL = 'textarea[placeholder="Type a message"]'


class FakeElement:
    def __init__(self, name, kind="textarea"):
        self.name = name
        self.kind = kind
        self.value = ""


class FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def type(self, text, delay=None):
        self.page.typed_into.append((self.page.focused.name, text))
        self.page.focused.value += text

    def press(self, key):
        self.page.keys.append((self.page.focused.name, key))
        if key == "Control+A":
            self.page.selected_all_on.append(self.page.focused.name)
        elif key == "Backspace":
            self.page.focused.value = ""
        elif key == "Escape":
            self.page.escapes += 1
            if self.page.escape_releases_focus:
                self.page.focus_thief = None


class FakeLocator:
    def __init__(self, el):
        self.first = self
        self._el = el

    def element_handle(self):
        return self._el


class FakePage:
    """Models DOM focus, and an optional overlay that keeps stealing it.

    focus_thief: element that grabs focus back after every click/focus attempt,
    standing in for the autocomplete dropdown.
    """

    def __init__(self, *, focus_thief=None, steal_limit=None,
                 click_raises=False, escape_releases_focus=False):
        self.box = FakeElement("message_box")
        self.thief = FakeElement("recipient_search", kind="input")
        self.focus_thief = self.thief if focus_thief else None
        self.steal_limit = steal_limit          # None = steals forever
        self.steals = 0
        self.click_raises = click_raises
        self.escape_releases_focus = escape_releases_focus
        self.focused = self.focus_thief or self.box
        self.typed_into = []
        self.keys = []
        self.selected_all_on = []
        self.escapes = 0
        self.keyboard = FakeKeyboard(self)

    def _settle(self):
        """Whoever we just focused loses it again while the thief is active."""
        if self.focus_thief is None:
            return
        if self.steal_limit is not None and self.steals >= self.steal_limit:
            self.focus_thief = None
            return
        self.steals += 1
        self.focused = self.focus_thief

    def click(self, sel, timeout=None):
        if self.click_raises:
            raise RuntimeError("intercepted by another element")
        self.focused = self.box
        self._settle()

    def focus(self, sel):
        self.focused = self.box
        self._settle()

    def locator(self, sel):
        return FakeLocator(self.box)

    def evaluate(self, expr, arg=None):
        if "activeElement" in expr and arg is not None:
            return arg is self.focused
        if ".focus()" in expr and arg is not None:
            self.focused = arg
            self._settle()
            return None
        return None

    def input_value(self, sel):
        return self.box.value

    def inner_text(self, sel):
        return self.box.value


def noop_log(_msg):
    pass


def test_types_into_the_message_box_when_focus_is_clean():
    page = FakePage()
    _type_multiline(page, MSG_SEL, "line one\nline two", noop_log)
    assert [name for name, _ in page.typed_into] == ["message_box", "message_box"]
    assert page.box.value == "line oneline two"


def test_recovers_when_the_overlay_releases_focus():
    # The dropdown steals focus once, then a retry gets through.
    page = FakePage(focus_thief=True, steal_limit=1)
    _type_multiline(page, MSG_SEL, "hello", noop_log)
    assert [name for name, _ in page.typed_into] == ["message_box"]


def test_refuses_to_type_when_focus_never_lands_in_the_message_box():
    page = FakePage(focus_thief=True)          # steals forever
    with pytest.raises(RuntimeError) as e:
        _type_multiline(page, MSG_SEL, "Hello! This is a reminder from Elite Prep", noop_log)
    assert "focus" in str(e.value).lower()
    # The whole point: not one character reached the contact search box.
    assert page.typed_into == []


def test_does_not_clear_a_field_it_does_not_own():
    """Ctrl+A + Backspace in the recipient box would wipe the recipient chips."""
    page = FakePage(focus_thief=True)
    with pytest.raises(RuntimeError):
        _type_multiline(page, MSG_SEL, "hello", noop_log)
    assert "recipient_search" not in page.selected_all_on
    assert page.thief.value == ""


def test_raises_when_the_click_is_intercepted():
    page = FakePage(focus_thief=True, click_raises=True)
    with pytest.raises(RuntimeError):
        _type_multiline(page, MSG_SEL, "hello", noop_log)
    assert page.typed_into == []


def test_dismisses_the_autocomplete_before_giving_up():
    page = FakePage(focus_thief=True, escape_releases_focus=True)
    _type_multiline(page, MSG_SEL, "hello", noop_log)
    assert page.escapes >= 1
    assert [name for name, _ in page.typed_into] == ["message_box"]
