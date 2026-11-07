"""Tests for reading the booking schedule from the business document
(smartdesk/booking/schedule.py). They read the real document.

Run with:  .venv/bin/python -m pytest tests/test_booking_schedule.py
"""

from datetime import time

from smartdesk.booking.schedule import Lesson, read_schedule
from smartdesk.business.store import get_knowledge

FRIDAY, MONDAY, WEDNESDAY = 4, 0, 2


def schedule():
    return read_schedule(get_knowledge())


def test_only_one_to_one_appointments_with_a_length_are_bookable():
    services = schedule().services
    assert services["Swedish Massage"].minutes == (60, 90) and services["Swedish Massage"].prices == (115, 160)
    assert "Private Yoga Session" in services
    assert services["Lip Wax"].minutes == (45,)
    # A group class and a package are booked other ways.
    assert not {"Vinyasa Flow", "Relax Package"} & set(services)


def test_each_staff_member_works_their_days_and_offers_their_specialties():
    team = schedule().staff_members
    dev = team["Dev Patel"]
    assert dev.days == {FRIDAY, 5, 6}
    assert set(dev.services) == {"Prenatal Massage", "Aromatherapy Massage", "Swedish Massage"}
    # A specialty can name a category ("body treatments") or part of a name ("private yoga").
    assert {"Body Scrub", "Mineral Body Wrap"} <= set(team["Eli Brooks"].services)
    assert team["Ana Lopez"].services == ("Private Yoga Session",)
    assert "Full Leg Wax" in team["Fay Kim"].services  # "hair removal (waxing)"


def test_who_offers_a_service():
    assert [t.name for t in schedule().staff_members_for("Swedish Massage")] == ["Cara Singh", "Dev Patel"]


def test_opening_hours_and_the_timetable_are_read():
    plan = schedule()
    assert plan.hours[FRIDAY] == (time(10), time(19)) and plan.hours[MONDAY] == (time(10), time(20))
    assert Lesson(WEDNESDAY, time(10), 60, "Prenatal Yoga", "Ana Lopez") in plan.lessons
