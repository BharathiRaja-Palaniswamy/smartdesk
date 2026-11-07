"""A stand-in calendar for tests, kept in memory, so a test never touches
the business's real Google calendars.

It has the same methods as the real one (smartdesk/booking/calendars/base.py),
so the booking rules run on it unchanged: a test passes it to Appointments
directly. The app itself always uses Google Calendar.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from smartdesk.booking.appointments import Appointments
from smartdesk.booking.calendars.base import Booking
from smartdesk.booking.schedule import read_schedule
from smartdesk.business.store import get_knowledge


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


SPA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 22, 14, 10, tzinfo=SPA)  # Thursday 22 October 2026, 2:10 PM at the business


def standin_desk(notice: int = 30, now=None) -> Appointments:
    """The booking rules over the real document and a fresh stand-in calendar, with the clock
    fixed at NOW (or `now`, a function giving the time) and `notice` minutes' notice to book."""
    return Appointments(read_schedule(get_knowledge()), MemoryCalendar(), SPA, 30, notice=notice,
                        now=now or (lambda: NOW))
