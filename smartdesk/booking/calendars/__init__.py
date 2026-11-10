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

The calendar is made once and kept; going live (onboarding) calls prepare(),
which makes it again for the business now live, so its staff, read from its
documents, each have a calendar before the first booking (go-live B4).
Resetting onboarding calls clear(), which removes every booking from the
business's calendars and keeps the calendars, so they stay shared.
"""

from functools import lru_cache

from ...config import get_settings
from .base import Booking, Calendar
from .google import connect, delete_bookings, make_google
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


def prepare() -> str:
    """Make the calendar again for the business now live (Google: create the calendar of
    each staff member who has none, shared with SMARTDESK_CALENDAR_OWNER), and say so
    in the owner's words. Raises CalendarUnavailable when it cannot be reached."""
    from ..errors import CalendarUnavailable

    get_calendar.cache_clear()
    if get_settings().calendar == "memory":
        get_calendar()
        return "Bookings are kept in a demo calendar, not Google Calendar."
    try:
        calendar = get_calendar()
    except Exception as error:  # Google's own errors, or no key: the owner hears it plainly
        raise CalendarUnavailable(f"Google Calendar could not be reached ({type(error).__name__}).") from error
    staff = len(getattr(calendar, "calendars", {}))
    return f"{staff} staff calendar{'s' * (staff != 1)} ready in Google Calendar."


def clear(business: str) -> str:
    """Remove every booking from `business`'s calendars (onboarding reset), keeping the
    calendars themselves (Google: still shared with the owner), and say what was
    removed. Raises CalendarUnavailable when Google cannot be reached."""
    from ..errors import CalendarUnavailable

    if get_settings().calendar == "memory":
        get_calendar.cache_clear()  # a new, empty demo calendar next time
        return "bookings in the demo calendar"
    try:
        deleted = delete_bookings(connect(), business)
    except CalendarUnavailable:
        raise
    except Exception as error:  # no key, or Google's own errors
        raise CalendarUnavailable(f"Google Calendar could not be reached ({type(error).__name__}).") from error
    get_calendar.cache_clear()
    return f"{deleted} booking{'s' * (deleted != 1)} from the calendars"
