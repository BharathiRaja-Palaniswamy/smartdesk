"""The waitlist's two ways back from the customer.

  GET  /api/widget/offer           has this chat's customer been offered a slot?
  POST /api/waitlist/answer/{id}   the key pressed on the keypad call (calls.py): 1 books, 2 lets it go

GET /api/widget/offer: has this chat's customer been offered a slot?

The widget asks every few seconds while it is open. The server finds the
customer of that conversation (the phone number it holds) and, if they have
an open offer not yet shown, writes the offer into the conversation as the
assistant's message (so the agent knows of it when they answer) and returns
its text for the widget to show. Each offer is shown once.
"""

import secrets
from datetime import datetime

from fastapi import APIRouter, Form, Query, Response
from pydantic import BaseModel

from ..frontdesk import customer_phone, tell
from ..frontdesk.staff import record_handoff
from .calls import ask, say, spoken_time
from .recovery import answer, mark_shown, offer_text, open_for, open_offer

router = APIRouter(prefix="/api/widget")
keypad = APIRouter(prefix="/api/waitlist")


class Offer(BaseModel):
    text: str
    suggestions: list[str]


@router.get("/offer")
def offer(thread: str = Query(min_length=8, max_length=64)) -> Offer | None:
    """The new offer for this conversation's customer, or nothing."""
    phone = customer_phone(thread)
    found = open_for(phone) if phone else None
    if found is None or found["shown"]:
        return None
    text = offer_text(found)
    tell(thread, text)
    mark_shown(found["id"])
    return Offer(text=text, suggestions=["Yes, book it", "No, thanks"])


def _twiml(body: str) -> Response:
    return Response(content=body, media_type="application/xml")


def _spelled(reference: str) -> str:
    """A booking reference said one character at a time: "B K 6 D 4 F 4 C"."""
    return " ".join(ch for ch in reference if ch.isalnum())


@keypad.post("/answer/{offer_id}")
def keypad_answer(offer_id: str, key: str = Query(max_length=64), Digits: str = Form(default="")) -> Response:
    """The key the customer pressed on the call about `offer_id` (Twilio sends it, with the
    offer's private key in the address). 1: the slot is booked for them, exactly as offered,
    if it is still free; 2: it is let go, and the next customer is called; anything else:
    the question is asked once more. Nothing is booked without their 1."""
    offer = open_offer(offer_id)
    if offer is None or not secrets.compare_digest(key, offer.get("key", "")):
        return _twiml(say("Sorry, this offer has ended. Goodbye."))
    if Digits == "1":
        result = answer(offer_id, offer["phone"], accept=True)
        if booked := result.get("booked"):
            b = booked[0]
            start = datetime.fromisoformat(b["start"])
            return _twiml(say(f"Wonderful, you're booked! {b['service']} with {b['staff_member']} on "
                              f"{start:%A %-d %B} at {spoken_time(start)}. Your reference is "
                              f"{_spelled(b['reference'])}. We look forward to seeing you. Bye for now!"))
        record_handoff(offer["name"], offer["phone"], f"Pressed 1 for offer {offer_id}, but it could not be booked: "
                       f"{result.get('error', 'unknown')}")
        return _twiml(say("Sorry, that time could not be booked. Our team will call you back. Goodbye."))
    if Digits == "2":
        answer(offer_id, offer["phone"], accept=False)
        return _twiml(say("No problem at all, we'll offer it to someone else. Thanks, and bye for now!"))
    return _twiml(ask(offer, again=True))
