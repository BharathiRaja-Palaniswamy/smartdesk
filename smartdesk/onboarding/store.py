"""Where the business's onboarded document is kept, and the draft waiting for its check.

    draft.md          the documents just read and cleaned, waiting for the safety check
    draft-check.json  what the safety check found in them (safety.py); empty when safe
    draft-schedule.json  what they say about booking: services, team, hours (booking.py)
    business.md       the document the agents use once live
    schedule.json     the booking schedule once live (business/store.get_schedule)
    phone.json        the business's phone line, when the owner asked for one (phone.py)

in the folder SMARTDESK_BUSINESS_FOLDER names (storage/business/ by default;
`storage/` is never committed: it holds a business's own data).

Going live needs the check to have run and found nothing (D31): ready() and
go_live() refuse otherwise, whatever the page sends. Going live replaces
business.md (and keeps the phone line, if one was given), then
forgets the parsed document (business/store.py), so the next question reads
the new one; search sees the new text and rebuilds its index on its own
(search/vectorstores/).

Demo build: one business. With cells (M2) this folder is the business's cell.
"""

import json
from dataclasses import asdict
from pathlib import Path

from ..config import get_settings
from .phone import Line


class Blocked(Exception):
    """Going live refused: the safety check found something, with the findings."""

    def __init__(self, findings: list[dict]):
        super().__init__(f"{len(findings)} findings")
        self.findings = findings


def _file(name: str) -> Path:
    """One of the business's files, in its folder."""
    return get_settings().business_folder / name


def _drafts() -> list[Path]:
    return [_file("draft.md"), _file("draft-check.json"), _file("draft-schedule.json")]


def save_draft(text: str) -> None:
    """Keep the documents just read until they are checked; forget any earlier reading of them."""
    _file("draft.md").parent.mkdir(parents=True, exist_ok=True)
    for stale in _drafts()[1:]:
        stale.unlink(missing_ok=True)
    _file("draft.md").write_text(text, encoding="utf-8")


def draft_path() -> Path:
    """Where the documents waiting to go live are. Raises FileNotFoundError when none was read."""
    if not _file("draft.md").exists():
        raise FileNotFoundError("draft.md")
    return _file("draft.md")


def draft_text() -> str:
    """The documents waiting to go live. Raises FileNotFoundError when none was read."""
    return _file("draft.md").read_text(encoding="utf-8")


def save_check(findings: list[dict]) -> None:
    """Keep what the safety check found in the draft (empty: nothing)."""
    _file("draft-check.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")


def checked() -> list[dict]:
    """What the safety check found. Raises FileNotFoundError when it has not run."""
    return json.loads(_file("draft-check.json").read_text(encoding="utf-8"))


def save_schedule(data: dict) -> None:
    """Keep what the draft says about booking (booking/schedule.schedule_data)."""
    _file("draft-schedule.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def ready() -> None:
    """Whether the draft may go live. Raises FileNotFoundError when the check or the
    booking reading has not run, and Blocked when the check found something."""
    findings = checked()
    if findings:
        raise Blocked(findings)
    if not _file("draft-schedule.json").exists():
        raise FileNotFoundError("draft-schedule.json")


def go_live(line: Line | None) -> None:
    """Make the checked draft the business's document, with its phone line when
    the owner asked for one. Raises as ready() does, before anything changes."""
    ready()
    _file("business.md").write_text(draft_text(), encoding="utf-8")
    _file("schedule.json").write_text(_file("draft-schedule.json").read_text(encoding="utf-8"), encoding="utf-8")
    if line:
        _file("phone.json").write_text(json.dumps(asdict(line), indent=2), encoding="utf-8")
    else:
        _file("phone.json").unlink(missing_ok=True)
    for draft in _drafts():
        draft.unlink(missing_ok=True)
    _forget()


def _forget() -> None:
    """Forget the parsed document, the schedule and the calendar made for the business
    before, so the next request reads the one live now. Imported here: business/store.py
    reads this module (live_document)."""
    from ..booking.calendars import get_calendar
    from ..business.store import get_knowledge, get_schedule

    get_knowledge.cache_clear()
    get_schedule.cache_clear()
    get_calendar.cache_clear()


def reset() -> list[str]:
    """Reset onboarding: forget the draft, the onboarded document, the phone line and the
    waitlist, so the business is onboarded again from the start. Returns what was
    removed, for the page to show. Its calendars and their bookings are removed
    before this (routes.py, booking/calendars.clear)."""
    removed = []
    if (live := _file("business.md")).exists():
        live.unlink()
        removed.append("onboarded document")
    _file("schedule.json").unlink(missing_ok=True)  # read from the document: goes with it
    if (phone := _file("phone.json")).exists():
        phone.unlink()  # its agent and secret are taken down first (routes.py, phone.tear_down)
        removed.append("phone line")
    waiting = [_file(name) for name in ("waitlist.json", "offers.json")]
    if any(path.exists() for path in waiting):  # they point at bookings that are gone with the calendars
        for path in waiting:
            path.unlink(missing_ok=True)
        removed.append("waitlist")
    if any(draft.exists() for draft in _drafts()):
        for draft in _drafts():
            draft.unlink(missing_ok=True)
        removed.append("unchecked upload")
    _forget()
    return removed


def live_document() -> Path | None:
    """The onboarded document, or None before the business has gone live."""
    live = _file("business.md")
    return live if live.exists() else None



def live_schedule() -> dict | None:
    """The booking schedule read at onboarding, as data; None before going live."""
    saved = _file("schedule.json")
    return json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else None


def live_phone() -> Line | None:
    """The business's phone line as set up at Go live, or None when it has none."""
    saved = _file("phone.json")
    return Line(**json.loads(saved.read_text(encoding="utf-8"))) if saved.exists() else None
