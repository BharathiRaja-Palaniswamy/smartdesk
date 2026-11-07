"""The one shared copy of the parsed business document.

Any part of the app that needs business facts calls `get_knowledge()`:
booking, the manage page's profile, and the assistants.
It lives here, not in app.py, so that route modules can import it without
importing app.py (which imports them, and would make a circular import).
"""

from functools import lru_cache
from pathlib import Path

from ..config import get_settings
from .knowledge import KnowledgeBase


@lru_cache  # runs once; every later call returns the same object
def get_knowledge() -> KnowledgeBase:
    """The business document, parsed. Read from disk on the first call only."""
    return KnowledgeBase(document_path())


def document_path() -> Path:
    """Where the business document is: SMARTDESK_DATA. SmartDesk holds no
    business's data, so there is no default; without it, this says what to set."""
    path = get_settings().data_path
    if path is None:
        raise RuntimeError("No business document: set SMARTDESK_DATA to the business's document (markdown).")
    return path
