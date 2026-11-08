"""Tests for the booking actions (smartdesk/booking/actions.py), run as the
booking would run them (smartdesk/agent/booking.py,
smartdesk/agent/booking.py): what a model sends and gets back, on the
real document, an in-memory calendar and a fixed clock.

Run with:  .venv/bin/python -m pytest tests/test_booking_actions.py
"""

from datetime import datetime

import pytest
from standin_calendar import standin_desk

from smartdesk.frontdesk import executor as approved
from smartdesk.frontdesk.booking import days_that_fit
from smartdesk.frontdesk.agent import agent_tools
from smartdesk.frontdesk.rules import MAX_DAYS

FRIDAY_10 = datetime(2026, 10, 23, 10, 0)


@pytest.fixture(autouse=True)
def desk(monkeypatch):
    """The actions book on one in-memory calendar, with "now" fixed on Thursday 22 October 2026."""
    desk = standin_desk(notice=0)
    for module in (approved,):
        monkeypatch.setattr(module, "get_appointments", lambda: desk)
    return desk


def test_the_agent_cannot_book_or_cancel_directly_only_ask_the_booking_agent():
    names = [t.name for t in agent_tools("Asha", "4085550101")]
    # The waitlist tools book nothing themselves: answer_offer books one offered slot, by code, on the customer's yes.
    assert names == ["search_guide", "booking", "record_feedback", "hand_off", "join_waitlist", "answer_offer"]


def test_a_customer_can_only_cancel_their_own_booking(desk):
    reference = desk.book("Prenatal Massage", "Dev Patel", FRIDAY_10, "Asha", "(408) 555-0101").id
    assert "No booking matches" in approved.cancel([reference], "408 555 9999")["not_cancelled"][0]
    assert approved.cancel([reference], "(408) 555-0101")["cancelled"][0]["reference"] == reference


def test_days_that_fit_are_the_days_every_service_has_a_free_time(desk):
    # The Event Prep Package: Eli (Vitamin C) works Tue-Sat, Fay (the rest) Mon, Wed, Thu, Sun.
    package = ["Vitamin C Facial", "Express Facial", "Eyebrow Wax"]
    days = days_that_fit(package, desk)
    assert days[:2] == ["Thursday 2026-10-22", "Wednesday 2026-10-28"]
    assert all(day.split()[0] in ("Wednesday", "Thursday") for day in days) and len(days) == MAX_DAYS


def test_a_day_whose_times_are_all_taken_is_not_offered(desk):
    for hour in range(10, 20):  # Fay's whole Wednesday is booked
        desk.book("Eyebrow Wax", "Fay Kim", datetime(2026, 10, 28, hour, 0), "Ben", "408 555 0102")
    days = days_that_fit(["Vitamin C Facial", "Eyebrow Wax"], desk)
    assert "Wednesday 2026-10-28" not in days
