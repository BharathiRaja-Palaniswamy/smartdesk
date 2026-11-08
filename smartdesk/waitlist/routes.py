"""GET /api/widget/offer: has this chat's customer been offered a slot?

The widget asks every few seconds while it is open. The server finds the
customer of that conversation (the phone number it holds) and, if they have
an open offer not yet shown, writes the offer into the conversation as the
assistant's message (so the agent knows of it when they answer) and returns
its text for the widget to show. Each offer is shown once.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..frontdesk import customer_phone, tell
from .recovery import mark_shown, offer_text, open_for

router = APIRouter(prefix="/api/widget")


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
