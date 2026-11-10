"""Tests for booking requests (smartdesk/agent/booking.py): a BookingRequest
in, a BookingResult out; code for complete requests, the model only for notes.

The model is a stand-in that plays back prepared answers (tests/standins.py),
so nothing is spent. The real document's schedule, an in-memory calendar and
a fixed clock (Thursday 22 October 2026, 2:10 PM).

Run with:  .venv/bin/python -m pytest tests/test_agent_booking.py
"""

from datetime import datetime

import pytest
from standin_calendar import standin_desk
from standins import use_standin

from smartdesk.frontdesk import booking
from smartdesk.frontdesk.booking import (
    BookingRequest,
    handle,
    missing_result,
)

ASHA = "(408) 555-0101"
EVENT_PREP = ["Vitamin C Facial", "Express Facial", "Eyebrow Wax"]


@pytest.fixture
def desk(monkeypatch):
    """One in-memory calendar with a fixed clock, for the agent and its tools."""
    desk = standin_desk()
    for module in (booking,):
        monkeypatch.setattr(module, "get_appointments", lambda: desk)
    return desk


def request(**fields) -> BookingRequest:
    return BookingRequest(**{"intent": "new", **fields})


# ---- in code: no model call ----------------------------------------------------------------

def test_a_service_with_no_day_or_time_gets_the_earliest_openings_to_choose_from(desk, monkeypatch):
    # Rule (2026-11-09): no time preference -> the earliest appointments, as choices.
    sent = use_standin(monkeypatch, [])
    result = handle(request(services=EVENT_PREP, package="Event Prep Package"), ASHA, desk)
    assert result.status == "options"
    assert result.options[:2] == ["Thursday 22 October at 3 PM with Eli Brooks",
                                  "Wednesday 28 October at 10 AM with Eli Brooks"]
    assert sent == []  # answered in code


def test_which_days_are_free_is_answered_with_the_earliest_openings(desk):
    result = handle(request(intent="availability", services=EVENT_PREP), ASHA, desk)
    assert result.status == "options" and "Wednesday 28 October at 10 AM with Eli Brooks" in result.options


def test_a_package_on_a_day_gets_a_plan_of_exactly_its_services(desk):
    result = handle(request(services=EVENT_PREP, day="2026-10-29"), ASHA, desk)
    assert result.status == "plan_ready"
    assert [(i.service, f"{i.start:%H:%M}") for i in result.plan.items] == [
        ("Vitamin C Facial", "10:00"), ("Express Facial", "11:00"), ("Eyebrow Wax", "11:30")]


def test_a_day_that_does_not_work_says_why_and_offers_other_days(desk):
    result = handle(request(services=EVENT_PREP, day="2026-10-27"), ASHA, desk)  # Fay is off on Tuesdays
    assert result.status == "not_possible" and "Express Facial" in result.reason
    assert result.reason.endswith("We are open 10 AM to 8 PM on Tuesdays.")  # the fact, so nothing is guessed
    assert "Wednesday 28 October at 10 AM with Eli Brooks" in result.options  # a time to pick, not just a day


def test_a_chosen_staff_member_is_kept(desk):
    result = handle(request(services=["Swedish Massage"], day="2026-10-30", staff_member="Dev Patel"), ASHA, desk)
    assert result.plan.items[0].staff_member == "Dev Patel"
    assert handle(request(services=["Swedish Massage"], staff_member="Nobody"), ASHA, desk).status == "not_possible"


def test_availability_gives_times_not_a_plan(desk):
    result = handle(request(intent="availability", services=["Prenatal Massage"], day="2026-10-30"), ASHA, desk)
    assert result.status == "options" and result.options[0].startswith("Prenatal Massage on Friday 30 October: 10 AM")


def test_availability_keeps_to_the_time_they_asked_for(desk):
    # "after 3pm" lists times from 15:00, the same window a booking keeps to.
    result = handle(request(intent="availability", services=["Prenatal Massage"], day="2026-10-30", after="15:00"),
                    ASHA, desk)
    assert result.options[0].startswith("Prenatal Massage on Friday 30 October: 3 PM")


def test_their_bookings_and_a_cancellation_to_approve(desk):
    mine = desk.book("Prenatal Massage", "Dev Patel", datetime(2026, 10, 30, 15, 0), "Asha", ASHA)
    desk.book("Prenatal Massage", "Dev Patel", datetime(2026, 10, 30, 16, 0), "Ben", "408 555 0102")
    assert [b["reference"] for b in handle(request(intent="my_bookings"), ASHA, desk).bookings] == [mine.id]
    result = handle(request(intent="cancel", references=[mine.id]), ASHA, desk)
    assert result.status == "cancel_ready" and [b["reference"] for b in result.cancel] == [mine.id]
    assert handle(request(intent="cancel", references=[mine.id]), "408 555 9999", desk).status == "not_possible"


def test_cancelling_part_of_a_package_goes_to_the_staff_and_all_of_it_can_be_cancelled(desk):
    package = "Event Prep Package"
    made = [desk.book(service, staff_member, datetime(2026, 10, 29, hour, minute), "Asha", ASHA, package=package)
            for service, staff_member, hour, minute in [("Vitamin C Facial", "Eli Brooks", 10, 0),
                                                      ("Express Facial", "Fay Kim", 11, 0),
                                                      ("Eyebrow Wax", "Fay Kim", 11, 30)]]
    part = handle(request(intent="cancel", references=[made[1].id]), ASHA, desk)
    assert part.status == "handoff" and "part of your Event Prep Package" in part.reason
    whole = handle(request(intent="cancel", references=[b.id for b in made]), ASHA, desk)
    assert whole.status == "cancel_ready" and len(whole.cancel) == 3
    # Changing one of them is changing part of it too.
    change = handle(request(intent="change", references=[made[2].id], services=["Eyebrow Wax"], day="2026-10-29"),
                    ASHA, desk)
    assert change.status == "handoff"


def test_a_change_without_a_reference_comes_with_their_bookings_to_choose_from(desk):
    desk.book("Prenatal Massage", "Dev Patel", datetime(2026, 10, 30, 15, 0), "Asha", ASHA)
    result = missing_result(request(intent="change", services=["Prenatal Massage"]), ["references"], ASHA, desk)
    assert result.missing == ["references"] and len(result.bookings) == 1


def test_a_change_names_the_booking_it_replaces(desk):
    old = desk.book("Prenatal Massage", "Dev Patel", datetime(2026, 10, 30, 11, 0), "Asha", ASHA)
    result = handle(request(intent="change", references=[old.id], services=["Prenatal Massage"], day="2026-10-30",
                            after="15:00"), ASHA, desk)
    assert result.status == "plan_ready" and result.replaces["reference"] == old.id
    assert result.replaces["service"] == "Prenatal Massage"  # what is cancelled, to say so in the question


def test_when_the_times_asked_for_are_taken_the_nearest_ones_are_offered(desk):
    # As seen live: "Friday morning", asked on a Friday afternoon, got "no free times" and nothing else.
    result = handle(request(intent="availability", services=["Swedish Massage"], day="2026-10-22", before="12:00"),
                    ASHA, desk)  # the clock: Thursday 22 October, 14:10, so this morning is over
    assert result.options[0] == "Swedish Massage on Thursday 22 October: no free times before 12:00"
    assert result.options[1].startswith("Swedish Massage on Thursday 22 October at other times: 3 PM with ")
    # Rule (2026-11-09): a morning asked for -> other mornings offered.
    assert result.options[2].startswith("Swedish Massage on other days, before 12:00: Friday 23 October at 10 AM with")


def test_the_days_offered_instead_keep_to_the_times_and_staff_member_asked_for(desk):
    # As seen live: "not Friday morning" offered Saturday, and the model promised "Saturday morning" unchecked.
    asked = request(services=["Swedish Massage"], day="2026-10-22", before="12:00", staff_member="Dev Patel")
    result = handle(asked, ASHA, desk)
    assert result.status == "not_possible"
    days = [option.split()[0] for option in result.options]
    assert days and set(days) <= {"Friday", "Saturday", "Sunday"}  # the days Dev works, with a morning time free
