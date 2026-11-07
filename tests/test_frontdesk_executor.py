"""Tests for the Plan, the plan check and the Executor (smartdesk/agent/booking.py, executor.py):
a Plan is booked all or nothing, re-checked at the yes, never double-booked.

The real document's schedule, a stand-in calendar and a fixed clock
(Thursday 22 October 2026, 2:10 PM); no model is called.

Run with:  .venv/bin/python -m pytest tests/test_agent_executor.py
"""

import threading
from datetime import datetime

from standin_calendar import SPA, standin_desk

from smartdesk.frontdesk.booking import Plan, PlanItem, check_plan
from smartdesk.frontdesk.executor import execute
from smartdesk.booking.calendars import Booking

FRIDAY = datetime(2026, 10, 30).date()


def item(service, staff_member, clock, minutes=None) -> PlanItem:
    hour, minute = map(int, clock.split(":"))
    return PlanItem(service=service, staff_member=staff_member, start=datetime(2026, 10, 30, hour, minute),
                    minutes=minutes)


MASSAGE_THEN_FACIAL = Plan(summary="A massage, then a facial, on Friday afternoon.", items=[
    item("Prenatal Massage", "Dev Patel", "14:00"), item("Signature Facial", "Eli Brooks", "15:30")])


def someone_else_books(desk, service, staff_member, clock):
    hour, minute = map(int, clock.split(":"))
    return desk.book(service, staff_member, datetime(2026, 10, 30, hour, minute), "Ben", "408 555 0102")


# ---- the plan check ----------------------------------------------------------------------

def test_a_plan_of_free_times_has_no_problems():
    assert check_plan(MASSAGE_THEN_FACIAL, standin_desk()) == []


def test_the_check_names_each_item_that_cannot_be_booked():
    plan = Plan(summary="", items=[item("Prenatal Massage", "Cara Singh", "14:00"),   # he doesn't offer it
                                   item("Signature Facial", "Eli Brooks", "19:30")])  # after closing
    problems = check_plan(plan, standin_desk())
    assert len(problems) == 2 and "does not offer" in problems[0] and "not a free time" in problems[1]


def test_one_customer_cannot_be_in_two_appointments_at_once():
    plan = Plan(summary="", items=[item("Prenatal Massage", "Dev Patel", "14:00"),
                                   item("Signature Facial", "Eli Brooks", "14:30")])
    assert "can't have both at once" in check_plan(plan, standin_desk())[0]


# ---- booking it ----------------------------------------------------------------------------

def test_an_approved_plan_is_booked_in_full():
    desk = standin_desk()
    outcome = execute(MASSAGE_THEN_FACIAL, "Asha Rao", "(408) 555-0101", desk)
    assert outcome.done and [b.staff_member for b in outcome.booked] == ["Dev Patel", "Eli Brooks"]
    assert all(b.phone == "(408) 555-0101" for b in desk.day_bookings(FRIDAY))


def test_a_time_taken_before_the_yes_books_nothing_and_says_which():
    desk = standin_desk()
    someone_else_books(desk, "Signature Facial", "Eli Brooks", "15:30")  # while Asha was deciding
    outcome = execute(MASSAGE_THEN_FACIAL, "Asha Rao", "(408) 555-0101", desk)
    assert not outcome.done and "Signature Facial with Eli Brooks" in outcome.problems[0]
    assert [b.name for b in desk.day_bookings(FRIDAY)] == ["Ben"]  # the massage was not booked alone


def test_a_failure_part_way_undoes_what_was_already_booked(monkeypatch):
    desk = standin_desk()
    real_book = desk.book

    def taken_in_between(service, staff_member, *args):
        # The facial is taken in the instant after the plan was checked.
        if service == "Signature Facial":
            real_book(service, staff_member, datetime(2026, 10, 30, 15, 30), "Ben", "408 555 0102")
        return real_book(service, staff_member, *args)
    monkeypatch.setattr(desk, "book", taken_in_between)
    outcome = execute(MASSAGE_THEN_FACIAL, "Asha Rao", "(408) 555-0101", desk)
    assert not outcome.done and [b.name for b in desk.day_bookings(FRIDAY)] == ["Ben"]


def test_an_event_typed_in_by_hand_at_the_same_moment_is_caught_and_undone(monkeypatch):
    desk = standin_desk()
    real_add = desk.calendar.add

    def owner_adds_too(booking):
        real_add(booking)
        if booking.staff_member == "Dev Patel":  # the owner blocks the same hour in Google Calendar
            real_add(Booking("BY-HAND", "Time off", "Dev Patel", booking.start, booking.end, "", ""))
    monkeypatch.setattr(desk.calendar, "add", owner_adds_too)
    outcome = execute(MASSAGE_THEN_FACIAL, "Asha Rao", "(408) 555-0101", desk)
    assert not outcome.done and "taken at the same moment" in outcome.problems[0]
    assert [b.id for b in desk.day_bookings(FRIDAY)] == ["BY-HAND"]  # Asha's bookings undone


def test_two_customers_approving_the_same_time_at_once_get_it_only_once():
    desk = standin_desk()
    plan = Plan(summary="", items=[item("Prenatal Massage", "Dev Patel", "14:00")])
    results = []

    def approve(n):
        results.append(execute(plan, f"Guest {n}", f"40855501{n:02}", desk))
    customers = [threading.Thread(target=approve, args=(n,)) for n in range(5)]
    for thread in customers:
        thread.start()
    for thread in customers:
        thread.join()
    assert sum(outcome.done for outcome in results) == 1
    assert len(desk.day_bookings(FRIDAY)) == 1


def test_the_spas_time_zone_is_used_for_a_time_given_without_one():
    outcome = execute(Plan(summary="", items=[item("Prenatal Massage", "Dev Patel", "14:00")]),
                      "Asha Rao", "(408) 555-0101", standin_desk())
    assert outcome.booked[0].start == datetime(2026, 10, 30, 14, 0, tzinfo=SPA)
