"""Tests for the chat widget's server side (smartdesk/widget/routes.py).

Run with:  .venv/bin/python -m pytest tests/test_widget.py
"""

import pytest
from fastapi.testclient import TestClient

from smartdesk.app import app

client = TestClient(app)


def test_the_widget_key_gives_the_business_and_its_greeting(monkeypatch):
    monkeypatch.setenv("SMARTDESK_WIDGET_KEY", "pub_test_123")
    monkeypatch.setenv("SMARTDESK_ASSISTANT_NAME", "Robin")
    business = client.get("/api/widget/business", params={"key": "pub_test_123"}).json()
    assert business["name"] == "Test Studio"
    assert business["greeting"].startswith("Hi! I'm Robin, Test Studio's assistant.")
    assert business["suggestions"]


def test_an_unknown_key_or_no_key_set_up_is_not_found(monkeypatch):
    monkeypatch.setenv("SMARTDESK_WIDGET_KEY", "pub_test_123")
    assert client.get("/api/widget/business", params={"key": "pub_guess"}).status_code == 404
    monkeypatch.setenv("SMARTDESK_WIDGET_KEY", "")
    assert client.get("/api/widget/business", params={"key": ""}).status_code == 404


def test_the_widget_and_the_preview_page_are_served():
    assert client.get("/web/widget/chat.js").status_code == 200
    assert client.get("/web/preview.html").status_code == 200


def test_the_preview_gives_the_widget_key_to_the_owner_only(monkeypatch):
    from conftest import signed_in

    monkeypatch.setenv("SMARTDESK_WIDGET_KEY", "pub_test_123")
    assert TestClient(app).get("/api/onboarding/preview").status_code == 401
    assert signed_in(app).get("/api/onboarding/preview").json() == {"key": "pub_test_123"}


def test_the_memory_calendar_is_chosen_by_setting(monkeypatch):
    from smartdesk.booking.calendars import get_calendar
    from smartdesk.booking.calendars.memory import MemoryCalendar

    monkeypatch.setenv("SMARTDESK_CALENDAR", "memory")
    get_calendar.cache_clear()
    try:
        assert isinstance(get_calendar(), MemoryCalendar)
    finally:
        get_calendar.cache_clear()


@pytest.mark.parametrize("page", ["onboard.html", "preview.html", "index.html", "admin.html"])
def test_every_id_on_a_page_is_used_once(page):
    # As seen live: the phone step and the business form's phone field were both
    # id="phone", so the step never showed. Pages find their parts by id.
    import re
    from collections import Counter

    ids = Counter(re.findall(r'\bid="([^"]+)"', client.get(f"/web/{page}").text))
    assert [name for name, count in ids.items() if count > 1] == []
