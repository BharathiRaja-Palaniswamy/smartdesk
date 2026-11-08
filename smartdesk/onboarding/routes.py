"""The owner's onboarding routes.

  POST /api/onboarding/read     the uploaded documents -> their text kept as a draft,
                                and the services table read from it
  POST /api/onboarding/go-live  the owner's services table -> the business goes live;
                                answers with the chat widget's snippet
  POST /api/onboarding/reset    {"confirm": <the business's name>} -> onboarding starts over

Both need the owner's sign-in (the "onboarding" permission).
"""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..access.session import require
from ..config import get_settings
from ..models import ModelError
from .readers import Unreadable, read
from .services import Service, read_services, titled
from .store import go_live, reset, save_draft

router = APIRouter(prefix="/api/onboarding", dependencies=[Depends(require("onboarding"))])
log = logging.getLogger("smartdesk.onboarding")
MAX_FILES = 30


class ReadDocument(BaseModel):
    name: str
    kind: str
    pages: int


class Row(BaseModel):
    """One row of the services table, as the page shows and sends it."""

    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="", max_length=120)
    minutes: int | None = Field(default=None, ge=5, le=600)
    price: float | None = Field(default=None, gt=0)
    quote: str = Field(default="", max_length=2000)  # the document's words it came from; "" when added by the owner


class ReadAnswer(BaseModel):
    documents: list[ReadDocument]
    services: list[Row]
    problems: list[str]


class GoLive(BaseModel):
    services: list[Row] = Field(min_length=1)


class Live(BaseModel):
    snippet: str  # what the owner pastes on their website


@router.post("/read")
async def read_documents(files: list[UploadFile], business: str = Form(min_length=1, max_length=120)) -> ReadAnswer:
    """Read the uploaded documents; their text waits as a draft until Go live.
    `business` is the name the owner gave in the first step: the document is
    titled with it when it has no title of its own (a PDF, a Word file)."""
    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Upload between 1 and {MAX_FILES} documents.")
    documents, problems = [], []
    for upload in files:
        try:
            documents.append(read(upload.filename or "document", await upload.read()))
        except Unreadable as reason:
            problems.append(str(reason))
    if not documents:
        raise HTTPException(status_code=422, detail=" ".join(problems) or "No document could be read.")
    text = titled("\n\n".join(document.text for document in documents), business)
    try:
        reading = read_services(text)
    except ModelError as error:
        log.warning("document reader unavailable: %s", error)
        raise HTTPException(status_code=503, detail="Reading is unavailable right now. Please try again.")
    save_draft(text)
    return ReadAnswer(documents=[ReadDocument(name=d.name, kind=d.kind, pages=d.pages) for d in documents],
                      services=[Row(**vars(s)) for s in reading.services], problems=problems + reading.problems)


@router.post("/go-live")
def go_live_route(body: GoLive, request: Request) -> Live:
    """Save the owner's services table and make the read documents the business's own."""
    try:
        go_live([Service(r.name, r.category, r.minutes, r.price, r.quote) for r in body.services])
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Read your documents first.")
    origin = str(request.base_url).rstrip("/")
    key = get_settings().widget_key
    return Live(snippet=f'<script src="{origin}/web/widget/chat.js"\n        data-business="{key}" defer></script>')


class Reset(BaseModel):
    confirm: str  # the business's name, typed by the owner


class ResetDone(BaseModel):
    removed: list[str]


@router.post("/reset")
def reset_route(body: Reset) -> ResetDone:
    """Start onboarding over, once the owner has typed the business's name."""
    from ..business.store import get_knowledge

    if body.confirm.strip() != get_knowledge().name:
        raise HTTPException(status_code=422, detail="Type the business's name exactly to confirm.")
    removed = reset()
    log.info("onboarding reset: %s", ", ".join(removed) or "nothing to remove")
    return ResetDone(removed=removed)
