"""The one shared copy of the parsed business document, and of its booking schedule.

Any part of the app that needs business facts calls `get_knowledge()`: the
manage page's profile and the assistants. Booking calls `get_schedule()`:
the schedule read at onboarding (any layout, D35), else the configured
document's, read by code from SmartDesk's layout.
It lives here, not in app.py, so that route modules can import it without
importing app.py (which imports them, and would make a circular import).
"""

from functools import lru_cache
from pathlib import Path

from ..booking.schedule import Schedule, read_schedule, schedule_from
from ..config import get_settings
from .knowledge import KnowledgeBase


@lru_cache  # runs once; every later call returns the same object
def get_knowledge() -> KnowledgeBase:
    """The business document, parsed. Read from disk on the first call only."""
    return KnowledgeBase(document_path())


@lru_cache
def get_schedule() -> Schedule:
    """What can be booked, with whom, and when. Read once; forgotten on going live and on reset."""
    from ..onboarding.store import live_schedule  # imported here, as in document_path

    data = live_schedule()
    return schedule_from(data) if data is not None else read_schedule(get_knowledge())


def document_path() -> Path:
    """Where the business document is: the one onboarded (onboarding/store.py),
    else the one SMARTDESK_DATA names. SmartDesk holds no business's data, so
    there is no default; without either, this says what to set."""
    from ..onboarding.store import live_document  # imported here: onboarding imports this module's users

    path = live_document() or get_settings().data_path
    if path is None:
        raise RuntimeError("No business document: onboard one, or set SMARTDESK_DATA to the business's document.")
    return path
