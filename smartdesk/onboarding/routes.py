"""The owner's onboarding routes.

  POST /api/onboarding/read     the uploaded documents -> their text, cleaned and kept as a draft
  POST /api/onboarding/check    the safety check on the draft (safety.py) -> what it found, if anything
  POST /api/onboarding/booking  what the draft says about booking (booking.py): services, team,
                                hours, in any layout (D35) -> a one-line headline, what was left out
  GET  /api/onboarding/preview  the widget key and the business's own facts (services, team,
                                hours, contact), for the owner's preview of their website (D33)
  GET  /api/onboarding/live     whether a business is onboarded here, and its name (the page's reset card)
  POST /api/onboarding/go-live  {"number": the business's number} -> the checked draft becomes the
                                business's document, its number is answered by its own agent
                                (D36, D37: phone support by default), and its staff calendars
                                are made ready (go-live B4);
                                answers with the widget's snippet and the line's number
  POST /api/onboarding/reset    {"confirm": <the business's name>} -> onboarding starts over

SmartDesk reads the documents as they are and asks the owner nothing about the
business (D31); it only checks they are safe for customers. All need the
owner's sign-in (the "onboarding" permission).
"""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..access.session import require
from ..config import get_settings
from ..models import ModelError
from . import phone
from ..booking.calendars import clear as clear_calendars
from ..booking.calendars import prepare as prepare_calendars
from ..booking.errors import CalendarUnavailable
from ..booking.schedule import schedule_data
from ..business.knowledge import KnowledgeBase
from .booking import read_booking
from .readers import Unreadable, read, titled
from .safety import check, clean
from .site import Site, site
from .store import (Blocked, checked, draft_path, draft_text, go_live, live_document, live_phone, ready, reset,
                    save_check, save_draft, save_schedule)

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


class Bookable(BaseModel):
    headline: str  # e.g. "6 services with 3 staff, open 6 days"
    services: int
    staff_members: int
    problems: list[str]  # what could not be booked, and why


class Onboarded(BaseModel):
    live: bool  # a business has gone live here (onboarding/store.live_document)
    name: str  # its name; "" when none has


class Preview(BaseModel):
    key: str  # the widget key the business's snippet carries
    site: Site  # what the stand-in website shows: the business's own facts


class GoLive(BaseModel):
    number: str = Field(max_length=32)  # the business's phone number, from the first step


class Live(BaseModel):
    snippet: str  # what the owner pastes on their website
    phone: str | None  # the number now answered by the assistant, as people write it; None when not set up
    phone_problem: str | None  # why the phone is not answered yet, in the owner's words
    calendars: str  # the staff calendars made ready for bookings, or why they are not


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


@router.post("/booking")
def booking_reading() -> Bookable:
    """Read what the checked draft says about booking, and keep it for going live."""
    try:
        if checked():
            raise HTTPException(status_code=409, detail="This document can't go live. Fix it and upload it again.")
        text = draft_text()
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Let the check finish first.")
    try:
        schedule, problems, how = read_booking(text, KnowledgeBase(draft_path()))
    except ModelError as error:
        log.warning("document reader unavailable: %s", error)
        raise HTTPException(status_code=503, detail="Reading is unavailable right now. Please try again.")
    save_schedule(schedule_data(schedule))
    log.info("booking read (%s): %d services, %d staff", how, len(schedule.services), len(schedule.staff_members))
    services, staff, days = len(schedule.services), len(schedule.staff_members), len(schedule.hours)
    headline = (f"{services} service{'s' * (services != 1)} with {staff} staff, open {days} day{'s' * (days != 1)}"
                if services else "No bookable services found: your assistant will answer questions only")
    return Bookable(headline=headline, services=services, staff_members=staff, problems=problems)


@router.get("/live")
def onboarded() -> Onboarded:
    """Whether a business has been onboarded here, for the page to offer resetting it.
    The configured document (SMARTDESK_DATA) is not one: only what went live through onboarding."""
    from ..business.store import get_knowledge

    if live_document() is None:
        return Onboarded(live=False, name="")
    return Onboarded(live=True, name=get_knowledge().name)


@router.get("/preview")
def preview() -> Preview:
    """The key the preview page adds the widget with, as the owner's website would.
    The preview is the live assistant: its bookings are real (D33)."""
    return Preview(key=get_settings().widget_key, site=site())


@router.post("/go-live")
def go_live_route(body: GoLive, request: Request) -> Live:
    """The checked documents become the business's own, and its number is answered by
    its own agent (D37). The website chat goes live even when the phone cannot be set
    up: the owner is told why, and nothing half-made is left behind."""
    try:
        ready()  # the documents first: nothing is set up for a document that cannot go live
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="Let the reading finish first.")
    except Blocked:
        raise HTTPException(status_code=409, detail="This document can't go live. Fix it and upload it again.")
    line, problem = None, None
    try:
        line = phone.set_up(KnowledgeBase(draft_path()).name, body.number)
    except phone.LineUnavailable as reason:
        problem = str(reason)
    try:
        go_live(line)
    except Exception:
        if line:
            phone.tear_down(line)  # nothing half-made is left behind
        raise
    try:
        calendars = prepare_calendars()  # the staff just read from the documents (go-live B4)
    except CalendarUnavailable as reason:
        log.warning("calendars not ready at go-live: %s", reason)
        calendars = f"{reason} Bookings will wait until it can be; the chat answers questions meanwhile."
    origin = str(request.base_url).rstrip("/")
    key = get_settings().widget_key
    return Live(snippet=f'<script src="{origin}/web/widget/chat.js"\n        data-business="{key}" defer></script>',
                phone=phone.shown(line.number) if line else None, phone_problem=problem, calendars=calendars)


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
    if line := live_phone():
        phone.tear_down(line)
    try:
        calendars = [clear_calendars(body.confirm.strip())]  # the business starts over: no bookings left
    except CalendarUnavailable as reason:
        log.warning("calendars not removed at reset: %s", reason)
        calendars = []
    removed = calendars + reset()
    log.info("onboarding reset: %s", ", ".join(removed) or "nothing to remove")
    return ResetDone(removed=removed)
