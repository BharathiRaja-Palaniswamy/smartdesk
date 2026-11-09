"""The owner's onboarding routes.

  POST /api/onboarding/read     the uploaded documents -> their text, cleaned and kept as a draft
  POST /api/onboarding/check    the safety check on the draft (safety.py) -> what it found, if anything
  GET  /api/onboarding/phone    whether phone support can be added, and what it costs (phone.py)
  GET  /api/onboarding/preview  the widget key, for the owner's preview of their website (D33)
  POST /api/onboarding/go-live  {"phone": bool, "agree_cost": bool} -> the checked draft becomes
                                the business's document, with a phone line if asked (D32);
                                answers with the widget's snippet and the line's number
  POST /api/onboarding/reset    {"confirm": <the business's name>} -> onboarding starts over

SmartDesk reads the documents as they are and asks the owner nothing about the
business (D31); it only checks they are safe for customers. All need the
owner's sign-in (the "onboarding" permission).
"""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, model_validator

from ..access.session import require
from ..config import get_settings
from ..models import ModelError
from . import phone
from .readers import Unreadable, read, titled
from .safety import check, clean
from .store import Blocked, draft_text, go_live, ready, reset, save_check, save_draft

router = APIRouter(prefix="/api/onboarding", dependencies=[Depends(require("onboarding"))])
log = logging.getLogger("smartdesk.onboarding")
MAX_FILES = 30


class ReadDocument(BaseModel):
    name: str
    kind: str
    pages: int


class ReadAnswer(BaseModel):
    documents: list[ReadDocument]
    problems: list[str]  # files that could not be used, and what was removed from the others


class Finding(BaseModel):
    kind: str
    why: str  # the kind in the owner's words, e.g. "violent or threatening words"
    quote: str  # the document's own words


class Checked(BaseModel):
    safe: bool
    findings: list[Finding]


class PhoneOffer(BaseModel):
    available: bool
    monthly: float  # dollars a month; the first month is free
    per_minute: float  # dollars a minute of calls received


class Preview(BaseModel):
    key: str  # the widget key the business's snippet carries


class GoLive(BaseModel):
    phone: bool = False  # the owner wants calls answered too
    agree_cost: bool = False  # and agreed to what the line costs

    @model_validator(mode="after")
    def _agreed(self) -> "GoLive":
        if self.phone and not self.agree_cost:
            raise ValueError("Agree to the phone line's cost to add phone support.")
        return self


class Live(BaseModel):
    snippet: str  # what the owner pastes on their website
    phone: str | None  # the phone line, as people write it; None without phone support


@router.post("/read")
async def read_documents(files: list[UploadFile], business: str = Form(min_length=1, max_length=120)) -> ReadAnswer:
    """Read the uploaded documents' text and clean it; it waits as a draft for its check.
    `business` is the name the owner gave in the first step: the text is titled
    with it when it has no title of its own (a PDF, a Word file)."""
    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Upload between 1 and {MAX_FILES} documents.")
    documents, texts, problems = [], [], []
    for upload in files:
        try:
            document = read(upload.filename or "document", await upload.read())
        except Unreadable as reason:
            problems.append(str(reason))
            continue
        text, removed = clean(document.text)
        if removed:
            problems.append(f"{document.name}: {' and '.join(removed)} removed")
        documents.append(document)
        texts.append(text)
    if not documents:
        raise HTTPException(status_code=422, detail=" ".join(problems) or "No document could be read.")
    save_draft(titled("\n\n".join(texts), business))
    return ReadAnswer(documents=[ReadDocument(name=d.name, kind=d.kind, pages=d.pages) for d in documents],
                      problems=problems)


@router.post("/check")
def check_draft() -> Checked:
    """Check the draft for what must not reach customers, and keep what was found."""
    try:
        text = draft_text()
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Upload your documents first.")
    try:
        findings = check(text)
    except ModelError as error:
        log.warning("safety check unavailable: %s", error)
        raise HTTPException(status_code=503, detail="The check is unavailable right now. Please try again.")
    save_check(findings)
    if findings:
        log.info("upload blocked: %s", ", ".join(sorted({f["kind"] for f in findings})))
    return Checked(safe=not findings, findings=[Finding(**f) for f in findings])


@router.get("/phone")
def phone_offer() -> PhoneOffer:
    """What the page tells the owner before they choose phone support."""
    return PhoneOffer(available=phone.available(), monthly=phone.MONTHLY, per_minute=phone.PER_MINUTE)


@router.get("/preview")
def preview() -> Preview:
    """The key the preview page adds the widget with, as the owner's website would.
    The preview is the live assistant: its bookings are real (D33)."""
    return Preview(key=get_settings().widget_key)


@router.post("/go-live")
def go_live_route(body: GoLive, request: Request) -> Live:
    """The checked documents become the business's own, with a phone line if the
    owner asked: all or nothing, the documents' check first."""
    try:
        ready()
        line = phone.get_line() if body.phone else None
        go_live(line)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Let the check finish first.")
    except Blocked:
        raise HTTPException(status_code=409, detail="This document can't go live. Fix it and upload it again.")
    except phone.LineUnavailable as reason:
        raise HTTPException(status_code=503, detail=str(reason))
    origin = str(request.base_url).rstrip("/")
    key = get_settings().widget_key
    return Live(snippet=f'<script src="{origin}/web/widget/chat.js"\n        data-business="{key}" defer></script>',
                phone=phone.shown(line.number) if line else None)


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
