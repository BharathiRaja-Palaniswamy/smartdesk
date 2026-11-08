"""The booking rules over the test business and a fresh in-memory calendar
(smartdesk/booking/calendars/memory.py), with the clock fixed, so a test never
touches a real calendar and always sees the same day.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from smartdesk.booking.appointments import Appointments
from smartdesk.booking.calendars.memory import MemoryCalendar
from smartdesk.booking.schedule import read_schedule
from smartdesk.business.store import get_knowledge


SPA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 22, 14, 10, tzinfo=SPA)  # Thursday 22 October 2026, 2:10 PM at the business


def standin_desk(notice: int = 30, now=None) -> Appointments:
    """The booking rules over the real document and a fresh stand-in calendar, with the clock
    fixed at NOW (or `now`, a function giving the time) and `notice` minutes' notice to book."""
    return Appointments(read_schedule(get_knowledge()), MemoryCalendar(), SPA, 30, notice=notice,
                        now=now or (lambda: NOW))
