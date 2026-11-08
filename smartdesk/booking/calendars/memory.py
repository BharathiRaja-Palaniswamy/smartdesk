"""A calendar kept in memory: the sandbox for demos, the simulator and tests.

It has the same methods as Google Calendar (base.py), so the booking rules run
on it unchanged. Nothing is written anywhere: bookings live in this process
and are gone when it stops, so a demo or a simulated chat can never reach a
business's real calendars. Chosen with SMARTDESK_CALENDAR=memory.
"""

from datetime import datetime

from .base import Booking


class MemoryCalendar:
    """A Calendar (see base.py) that keeps bookings in a dictionary."""

    def __init__(self) -> None:
        self._bookings: dict[str, Booking] = {}  # by reference

    def busy(self, staff_member: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """The staff member's bookings that overlap `start`..`end`."""
        return [(b.start, b.end) for b in self.bookings(start, end, staff_member)]

    def add(self, booking: Booking) -> None:
        """Keep `booking`."""
        self._bookings[booking.id] = booking

    def find(self, booking_id: str) -> Booking | None:
        """The booking with this reference, or None."""
        return self._bookings.get(booking_id)

    def remove(self, booking_id: str) -> None:
        """Forget the booking with this reference."""
        self._bookings.pop(booking_id, None)

    def bookings(self, start: datetime, end: datetime, staff_member: str | None = None) -> list[Booking]:
        """The bookings that overlap `start`..`end`, earliest first."""
        found = [b for b in self._bookings.values()
                 if b.start < end and b.end > start and staff_member in (None, b.staff_member)]
        return sorted(found, key=lambda b: b.start)
