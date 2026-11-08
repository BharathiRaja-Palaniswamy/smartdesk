"""Where bookings are kept.

`get_calendar()` is the only way the rest of the app gets the calendar. Which
one is a setting, SMARTDESK_CALENDAR:

  google  the business's Google calendars (google.py), one per staff member,
          signed in with GOOGLE_SERVICE_ACCOUNT (the default). If Google cannot
          be reached, booking says so (CalendarUnavailable) rather than quietly
          keeping bookings somewhere else.
  memory  a sandbox kept in memory (memory.py), for demos, the simulator and
          tests: nothing reaches a real calendar, and bookings are gone when
          the app stops.

The booking rules only use the methods in base.py, so another calendar
(Outlook, say) would be a new file with those methods.
"""

from functools import lru_cache

from ...config import get_settings
from .base import Booking, Calendar
from .google import make_google
from .memory import MemoryCalendar

__all__ = ["Booking", "Calendar", "get_calendar"]


@lru_cache  # one calendar for the whole server; a failed attempt is not kept, so the next request tries again
def get_calendar() -> Calendar:
    """The calendar SMARTDESK_CALENDAR names."""
    choice = get_settings().calendar
    if choice == "memory":
        return MemoryCalendar()
    if choice != "google":
        raise ValueError(f"Unknown SMARTDESK_CALENDAR: {choice!r}. Choose google or memory.")
    return make_google()
