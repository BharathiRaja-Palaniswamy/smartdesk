"""Tests for slot recovery, the empty chair (smartdesk/waitlist/).

The booking rules run over the test business and an in-memory calendar with a
fixed clock (standin_calendar.py); the waitlist and offers live in a folder of
the test's own. No model is called.

Run with:  .venv/bin/python -m pytest tests/test_waitlist.py
"""

from datetime import date, datetime, time, timedelta

import pytest
from standin_calendar import NOW, SPA, standin_desk

from smartdesk.frontdesk import executor
from smartdesk.waitlist import recovery
from smartdesk.waitlist.store import load

FRIDAY = date(2026, 10, 23)
THREE_PM = datetime(2026, 10, 23, 15, 0, tzinfo=SPA)
ASHA, BEN, CARA = "(555) 010-0001", "(555) 010-0002", "(555) 010-0003"


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """One calendar for the whole test, a fixed clock, and the test's own folder."""
    monkeypatch.setenv("SMARTDESK_BUSINESS_FOLDER", str(tmp_path))
    the_desk = standin_desk()
    monkeypatch.setattr(executor, "get_appointments", lambda: the_desk)
    monkeypatch.setattr(recovery, "get_appointments", lambda: the_desk)
    monkeypatch.setattr(recovery, "_now", lambda: NOW)
    return the_desk


def booked_and_cancelled(desk) -> None:
    """Asha books Friday 3 pm with Dev, then cancels it: the slot opens."""
    reference = desk.book("Prenatal Massage", "Dev Patel", THREE_PM, "Asha", ASHA).id
    executor.cancel([reference], ASHA)


def test_a_cancelled_slot_is_offered_to_the_earliest_matching_waiter_only(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offers = load("offers")
    assert [(o["name"], o["start"], o["status"]) for o in offers] == [("Ben", THREE_PM.isoformat(), "open")]
    assert recovery.open_for(CARA) is None


def test_a_waiter_for_another_service_day_or_window_is_not_offered(desk):
    recovery.join("Ben", BEN, "Swedish Massage", FRIDAY)  # another service
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY, before=time(12, 0))  # mornings only
    booked_and_cancelled(desk)
    assert load("offers") == []


def test_yes_books_exactly_the_offered_slot(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offer = recovery.open_for(BEN)
    result = recovery.answer(offer["id"], BEN, accept=True)
    assert result["booked"]["staff_member"] == "Dev Patel"
    [booking] = desk.calendar.bookings(THREE_PM, THREE_PM + timedelta(hours=1))
    assert (booking.name, booking.phone, booking.start) == ("Ben", BEN, THREE_PM)
    assert load("waitlist")[0]["status"] == "booked"


def test_no_offers_the_slot_to_the_next_waiter(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    assert recovery.answer(recovery.open_for(BEN)["id"], BEN, accept=False) == {"declined": True}
    assert recovery.open_for(CARA)["start"] == THREE_PM.isoformat()
    assert recovery.open_for(BEN) is None  # never offered that slot again


def test_an_offer_not_answered_in_time_goes_to_the_next_waiter(desk, monkeypatch):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    monkeypatch.setattr(recovery, "_now", lambda: NOW + timedelta(minutes=16))
    assert recovery.open_for(BEN) is None
    assert recovery.open_for(CARA) is not None


def test_a_slot_taken_meanwhile_is_not_booked_on_yes(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    desk.book("Prenatal Massage", "Dev Patel", THREE_PM, "Walk-in", "(555) 010-0009")  # taken at the desk
    result = recovery.answer(recovery.open_for(BEN)["id"], BEN, accept=True)
    assert "could not be booked" in result["error"]


def test_only_the_offered_customer_can_answer_it(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offer = recovery.open_for(BEN)
    assert "no open offer" in recovery.answer(offer["id"], CARA, accept=True)["error"]


def test_the_widget_is_shown_its_customers_offer_once_and_the_agent_hears_of_it(desk, monkeypatch):
    from fastapi.testclient import TestClient

    from smartdesk import frontdesk
    from smartdesk.app import app
    from smartdesk.waitlist import routes

    told = []
    monkeypatch.setattr(routes, "customer_phone", lambda thread: BEN if thread == "ben-chat-1" else "")
    monkeypatch.setattr(routes, "tell", lambda thread, text: told.append((thread, text)))
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    client = TestClient(app)
    first = client.get("/api/widget/offer", params={"thread": "ben-chat-1"}).json()
    assert first["text"].startswith("Good news, Ben: a Prenatal Massage with Dev Patel on Friday 23 October at 15:00")
    assert first["suggestions"] == ["Yes, book it", "No, thanks"]
    assert told == [("ben-chat-1", first["text"])]  # written into Ben's conversation
    assert client.get("/api/widget/offer", params={"thread": "ben-chat-1"}).json() is None  # shown once
    assert client.get("/api/widget/offer", params={"thread": "someone-else"}).json() is None
    assert frontdesk.customer_phone  # the real lookup exists
