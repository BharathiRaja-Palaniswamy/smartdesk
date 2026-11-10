"""GET /api/widget/business: the business a widget key belongs to."""

import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..business.store import get_knowledge
from ..config import get_settings

router = APIRouter(prefix="/api/widget")

SUGGESTIONS = ["What services do you offer?", "Book an appointment", "Opening hours"]


class WidgetBusiness(BaseModel):
    """What the widget shows before the first message."""

    name: str
    greeting: str
    suggestions: list[str]


@router.get("/business")
def business(key: str) -> WidgetBusiness:
    """The business for `key`, or 404 when the key is not one of ours."""
    expected = get_settings().widget_key
    # compare_digest: the time taken does not reveal how much of a guess was right.
    if not expected or not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=404, detail="This chat isn't set up for this website.")
    name, assistant = get_knowledge().name, get_settings().assistant_name
    me = f"I'm {assistant}, {name}'s assistant" if assistant else f"I'm {name}'s assistant"
    return WidgetBusiness(name=name, suggestions=SUGGESTIONS,
                          greeting=f"Hi! {me}. I can answer your questions and help you book. What can I do for you?")
