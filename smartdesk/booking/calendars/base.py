"""The interface every calendar follows, and the booking it keeps.

The business has one calendar per staff member ("Test Studio – Dev Patel", ...). A
Calendar here stands for all of them together: every method names the
staff member whose calendar it reads or writes. The owner sees them side by
side in Google Calendar; the app never needs to.

A calendar holds what the document cannot: the bookings, and anything else
that makes a staff member busy (in Google Calendar, an event a staff member adds
for time off). It knows nothing about services, opening hours or booking
rules; those are in schedule.py and appointments.py, so a calendar is easy
to swap: Google Calendar in the app (google.py), a stand-in in the tests.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Booking:
    """One confirmed appointment."""

    id: str  # our reference, e.g. "BK-7F3A2C", told to the customer
    service: str
    staff_member: str
    start: datetime  # with its time zone (the business's)
    end: datetime
    name: str  # the customer's
    phone: str
    package: str = ""  # the package it was booked as part of, e.g. "Event Prep Package"; "" for none
    add_ons: tuple[str, ...] = ()  # extras the customer asked for with it, e.g. ("Scalp massage",)


class Calendar(Protocol):
    """Reads and writes the staff members' calendars."""

    def busy(self, staff_member: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """Every period between `start` and `end` when `staff member` is not free:
        their bookings, and any other event on their calendar."""
        ...

    def add(self, booking: Booking) -> None:
        """Put `booking` on its staff member's calendar."""
        ...

    def find(self, booking_id: str) -> Booking | None:
        """The booking with this reference, or None."""
        ...

    def remove(self, booking_id: str) -> None:
        """Take the booking with this reference off its calendar."""
        ...

    def bookings(self, start: datetime, end: datetime, staff_member: str | None = None) -> list[Booking]:
        """The bookings between `start` and `end`, earliest first; one
        staff member's, or everyone's when `staff member` is None."""
        ...
