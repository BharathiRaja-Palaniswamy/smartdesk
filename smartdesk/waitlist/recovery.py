"""Who waits, who is offered a cancelled slot, and what their answer does.

    join      a customer who agreed to wait for a service on a day (and,
              optionally, starting within a time window, both ends included,
              so 15:00 to 15:00 is "3 pm only") is added, with when they agreed
    opened    a slot opened by a cancellation is offered to the earliest-joined
              waiter who wants it, one at a time, for SMARTDESK_OFFER_MINUTES
    answer    yes books exactly that slot (checked free again); no closes the
              offer and the next waiter is offered
    open_for  the open offer for a phone number, after closing any that expired
              (and offering their slot to the next waiter)

All of it is code: the Front Desk agent only hears the customer and calls
its tools. Rules in docs/workflows/slot-recovery.md.
"""

import secrets
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..booking.actions import confirmation
from ..booking.appointments import digits, get_appointments
from ..booking.calendars.base import Booking
from ..booking.errors import BookingError, CalendarUnavailable
from ..config import get_settings
from .store import change, load


def _now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def _slot_key(offer_or_booking: dict[str, Any]) -> str:
    return f"{offer_or_booking['service']}|{offer_or_booking['staff_member']}|{offer_or_booking['start']}"


def join(name: str, phone: str, service: str, day: date, after: time | None = None,
         before: time | None = None) -> dict[str, Any]:
    """Add the customer to the waitlist (they agreed to wait). Returns their entry."""
    entry = {"id": "WL-" + secrets.token_hex(3).upper(), "name": name, "phone": phone, "service": service,
             "day": day.isoformat(), "after": after.strftime("%H:%M") if after else "",
             "before": before.strftime("%H:%M") if before else "", "joined_at": _now().isoformat(),
             "status": "waiting", "declined": []}
    change("waitlist", lambda rows: rows.append(entry))
    return entry


def _wants(entry: dict[str, Any], slot: dict[str, Any]) -> bool:
    """Whether the waiting `entry` wants the opened `slot`."""
    start = datetime.fromisoformat(slot["start"])
    return (entry["status"] == "waiting" and entry["service"] == slot["service"]
            and entry["day"] == start.date().isoformat()
            and (not entry["after"] or start.strftime("%H:%M") >= entry["after"])
            and (not entry["before"] or start.strftime("%H:%M") <= entry["before"])  # "3 pm only" is 15:00 to 15:00
            and digits(entry["phone"]) != digits(slot.get("freed_by", ""))
            and _slot_key(slot) not in entry["declined"])


def _offer(slot: dict[str, Any]) -> dict[str, Any] | None:
    """Offer `slot` to the earliest-joined waiter who wants it; None if nobody does."""
    def pick(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
        waiting = sorted((e for e in entries if _wants(e, slot)), key=lambda e: e["joined_at"])
        if not waiting:
            return None
        waiting[0]["status"] = "offered"
        return waiting[0]

    entry = change("waitlist", pick)
    if entry is None:
        return None
    now = _now()
    offer = {"id": "OF-" + secrets.token_hex(3).upper(), "entry": entry["id"], "name": entry["name"],
             "phone": entry["phone"], "service": slot["service"], "staff_member": slot["staff_member"],
             "start": slot["start"], "minutes": slot["minutes"], "freed_by": slot.get("freed_by", ""),
             "offered_at": now.isoformat(),
             "expires_at": (now + timedelta(minutes=get_settings().offer_minutes)).isoformat(),
             "status": "open", "shown": False}
    change("offers", lambda rows: rows.append(offer))
    return offer


def opened(booking: Booking) -> dict[str, Any] | None:
    """A cancellation freed `booking`'s slot: offer it to the next waiter, if any."""
    _expire()
    slot = {"service": booking.service, "staff_member": booking.staff_member, "start": booking.start.isoformat(),
            "minutes": int((booking.end - booking.start).total_seconds() // 60), "freed_by": booking.phone}
    return _offer(slot)


def _close(offer_id: str, status: str) -> dict[str, Any] | None:
    """Close the open offer `offer_id` with `status`; its waiter goes back to waiting
    (except after a booking), never offered that slot again. Returns the offer."""
    def close(offers: list[dict[str, Any]]) -> dict[str, Any] | None:
        offer = next((o for o in offers if o["id"] == offer_id and o["status"] == "open"), None)
        if offer:
            offer["status"] = status
        return offer

    offer = change("offers", close)
    if offer:
        def release(entries: list[dict[str, Any]]) -> None:
            for entry in entries:
                if entry["id"] == offer["entry"]:
                    entry["status"] = "booked" if status == "accepted" else "waiting"
                    entry["declined"].append(_slot_key(offer))
        change("waitlist", release)
    return offer


def _expire() -> None:
    """Close every open offer past its time, and offer its slot to the next waiter."""
    now = _now()
    for offer in load("offers"):
        if offer["status"] == "open" and datetime.fromisoformat(offer["expires_at"]) <= now:
            if _close(offer["id"], "expired"):
                _offer(offer)


def open_for(phone: str) -> dict[str, Any] | None:
    """The open offer for this phone number, if any."""
    _expire()
    return next((o for o in load("offers")
                 if o["status"] == "open" and digits(o["phone"]) == digits(phone)), None)


def mark_shown(offer_id: str) -> None:
    """Remember the offer has been shown in the customer's chat."""
    def mark(offers: list[dict[str, Any]]) -> None:
        for offer in offers:
            if offer["id"] == offer_id:
                offer["shown"] = True
    change("offers", mark)


def answer(offer_id: str, phone: str, accept: bool) -> dict[str, Any]:
    """The customer's answer to their offer: yes books that exact slot, no lets it go."""
    offer = open_for(phone)
    if offer is None or offer["id"] != offer_id.strip().upper():
        return {"error": "There is no open offer with that reference for this customer (it may have expired)."}
    if not accept:
        _close(offer["id"], "declined")
        _offer(offer)  # the next waiter
        return {"declined": True}
    try:
        booking = get_appointments().book(offer["service"], offer["staff_member"],
                                          datetime.fromisoformat(offer["start"]), offer["name"], offer["phone"],
                                          minutes=offer["minutes"])
    except (BookingError, CalendarUnavailable) as error:
        _close(offer["id"], "failed")
        return {"error": f"That time could not be booked: {error}"}
    _close(offer["id"], "accepted")
    return {"booked": [confirmation(booking)]}  # a list, as every booking result is (executor.py)


def offer_text(offer: dict[str, Any]) -> str:
    """The offer as the customer reads it in their chat."""
    start = datetime.fromisoformat(offer["start"])
    until = datetime.fromisoformat(offer["expires_at"])
    return (f"Good news, {offer['name']}: a {offer['service']} with {offer['staff_member']} on "
            f"{start:%A %d %B} at {start:%H:%M} just opened up. Would you like it? I'm holding it for you "
            f"until {until:%H:%M}. (Offer {offer['id']})")
