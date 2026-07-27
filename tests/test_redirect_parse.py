"""The test-redirect box must never silently merge numbers into one bad number."""

import importlib.util
import pathlib
import sys
import types

import pytest

BASE = pathlib.Path(__file__).resolve().parents[1]


def _load_parse_redirect():
    """Import parse_redirect from app.py without executing the Streamlit page."""
    sys.modules.setdefault("streamlit", types.ModuleType("streamlit"))
    src = (BASE / "app.py").read_text(encoding="utf-8")
    start = src.index("def parse_redirect")
    end = src.index("\n# ---------- cached resources ----------")
    mod = types.ModuleType("_parse_redirect_only")
    mod.__dict__["re"] = __import__("re")
    from sms.gv_sender import normalize_phone_number
    mod.__dict__["normalize_phone_number"] = normalize_phone_number
    exec(compile(src[start:end], "app.py", "exec"), mod.__dict__)
    return mod.parse_redirect


parse_redirect = _load_parse_redirect()


@pytest.mark.parametrize("text, good, bad", [
    ("", [], []),
    ("714-300-3245", ["7143003245"], []),
    ("(714) 300-3245", ["7143003245"], []),
    ("714-300-3245, 470-555-0100", ["7143003245", "4705550100"], []),
    ("714-300-3245; 470-555-0100", ["7143003245", "4705550100"], []),
    ("714-300-3245\n470-555-0100", ["7143003245", "4705550100"], []),
    ("17143003245", ["17143003245"], []),
    ("714-300-3245, 714-300-3245", ["7143003245"], []),      # de-duped
    ("714-300-3245, 12345", ["7143003245"], ["12345"]),      # too short flagged
    ("nonsense", [], ["nonsense"]),
])
def test_parse_redirect(text, good, bad):
    assert parse_redirect(text) == (good, bad)


def test_two_numbers_are_not_glued_together():
    """The bug this guards: two numbers becoming one 20-digit string."""
    good, _ = parse_redirect("714-300-3245, 470-555-0100")
    assert "71430032454705550100" not in good
    assert len(good) == 2
    assert all(len(n) == 10 for n in good)
