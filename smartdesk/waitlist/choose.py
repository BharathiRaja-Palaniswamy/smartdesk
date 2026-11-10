"""Who is offered an opened slot, and for how long it is held (D34).

Everyone who can take the slot (recovery._wants: the service, the day, their
time window, not the customer who cancelled it, not a slot they turned down)
is ranked, best first:

    1. exactness   who asked for exactly that time, then a window (the
                   narrower the better), then any time that day: the more
                   precisely they wanted it, the likelier they say yes
    2. reliability fewer offers let run out without an answer before
    3. waiting     who joined the waitlist first

The hold follows how soon the slot is: a slot in two hours is held about
ten minutes, one tomorrow or later for the longest hold
(SMARTDESK_OFFER_MINUTES), so a near slot gets several chances before it
starts. A slot too near to answer and still arrive for is offered to nobody.

All of it is code: the same waitlist always gives the same choice.
"""

from datetime import datetime, timedelta
from typing import Any

from ..booking.appointments import digits
from ..config import get_settings

MIN_HOLD = 5  # minutes: the shortest time a customer is given to answer
HOLD_SHARE = 12  # a slot this many holds away is held for one: 2 hours ahead -> 10 minutes


def hold(start: datetime, now: datetime) -> timedelta | None:
    """How long an offer for a slot at `start` is held, or None when the slot is too
    near: the answer must come, and leave the minimum notice, before it starts."""
    settings = get_settings()
    usable = start - now - timedelta(minutes=settings.min_notice_minutes)
    held = min(timedelta(minutes=settings.offer_minutes), max(timedelta(minutes=MIN_HOLD), (start - now) / HOLD_SHARE))
    held = min(held, usable)
    return held if held >= timedelta(minutes=MIN_HOLD) else None


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _exactness(entry: dict[str, Any]) -> tuple[int, int]:
    """0 for one exact time, 1 for a window (narrower first), 2 for any time."""
    if not entry["after"] and not entry["before"]:
        return 2, 0
    if entry["after"] and entry["after"] == entry["before"]:
        return 0, 0
    width = _minutes(entry["before"] or "23:59") - _minutes(entry["after"] or "00:00")
    return 1, width


def rank(waiting: list[dict[str, Any]], offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The waiters who can take a slot, best first (see above). `offers` are all
    offers so far: an offer that expired unanswered counts against its customer."""
    def missed(entry: dict[str, Any]) -> int:
        return sum(1 for offer in offers
                   if offer["status"] == "expired" and digits(offer["phone"]) == digits(entry["phone"]))

    return sorted(waiting, key=lambda entry: (_exactness(entry), missed(entry), entry["joined_at"]))
