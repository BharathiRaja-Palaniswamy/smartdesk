"""Where the business's onboarded document is kept, and the draft waiting for its check.

    draft.md          the documents just read and cleaned, waiting for the safety check
    draft-check.json  what the safety check found in them (safety.py); empty when safe
    business.md       the document the agents use once live
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
    return [_file("draft.md"), _file("draft-check.json")]


def save_draft(text: str) -> None:
    """Keep the documents just read until they are checked; forget any earlier check."""
    _file("draft.md").parent.mkdir(parents=True, exist_ok=True)
    _file("draft-check.json").unlink(missing_ok=True)
    _file("draft.md").write_text(text, encoding="utf-8")


def draft_text() -> str:
    """The documents waiting to go live. Raises FileNotFoundError when none was read."""
    return _file("draft.md").read_text(encoding="utf-8")


def save_check(findings: list[dict]) -> None:
    """Keep what the safety check found in the draft (empty: nothing)."""
    _file("draft-check.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")


def checked() -> list[dict]:
    """What the safety check found. Raises FileNotFoundError when it has not run."""
    return json.loads(_file("draft-check.json").read_text(encoding="utf-8"))


def ready() -> None:
    """Whether the draft may go live. Raises FileNotFoundError when the check has
    not run, and Blocked when it found something."""
    findings = checked()
    if findings:
        raise Blocked(findings)


def go_live(line: Line | None) -> None:
    """Make the checked draft the business's document, with its phone line when
    the owner asked for one. Raises as ready() does, before anything changes."""
    from ..business.store import get_knowledge  # imported here: business/store.py reads live_document

    ready()
    _file("business.md").write_text(draft_text(), encoding="utf-8")
    if line:
        _file("phone.json").write_text(json.dumps(asdict(line), indent=2), encoding="utf-8")
    else:
        _file("phone.json").unlink(missing_ok=True)
    for draft in _drafts():
        draft.unlink(missing_ok=True)
    get_knowledge.cache_clear()


def reset() -> list[str]:
    """Reset onboarding: forget the draft, the onboarded document and the phone line, so the business
    is onboarded again from the start. Returns what was removed, for the page to
    show. Customers' bookings are not touched."""
    from ..business.store import get_knowledge

    removed = []
    if (live := _file("business.md")).exists():
        live.unlink()
        removed.append("onboarded document")
    if (phone := _file("phone.json")).exists():
        phone.unlink()  # demo build: the line is only unassigned; nothing was bought
        removed.append("phone line")
    if any(draft.exists() for draft in _drafts()):
        for draft in _drafts():
            draft.unlink(missing_ok=True)
        removed.append("unchecked upload")
    get_knowledge.cache_clear()
    return removed


def live_document() -> Path | None:
    """The onboarded document, or None before the business has gone live."""
    live = _file("business.md")
    return live if live.exists() else None

