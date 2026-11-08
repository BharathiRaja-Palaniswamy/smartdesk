"""Where the business's onboarded document and services table are kept.

    draft.md       the documents just read, waiting for "Go live"
    business.md    the document the agents use once live
    services.json  the services table, as the owner saved it

in the folder SMARTDESK_BUSINESS_FOLDER names (storage/business/ by default;
`storage/` is never committed: it holds a business's own data).
Going live replaces business.md and services.json together, then forgets the
parsed document (business/store.py), so the next question reads the new one;
search sees the new text and rebuilds its index on its own (search/vectorstores/).

Demo build: one business. With cells (M2) this folder is the business's cell.
"""

import json
from dataclasses import asdict
from pathlib import Path

from ..config import get_settings
from .services import Service


def _file(name: str) -> Path:
    """One of the business's files, in its folder."""
    return get_settings().business_folder / name


def save_draft(text: str) -> None:
    """Keep the documents just read until the owner goes live."""
    _file("draft.md").parent.mkdir(parents=True, exist_ok=True)
    _file("draft.md").write_text(text, encoding="utf-8")


def go_live(services: list[Service]) -> None:
    """Make the draft the business's document, with its services table.
    Raises FileNotFoundError when no document was read first."""
    from ..business.store import get_knowledge  # imported here: business/store.py reads live_document

    draft = _file("draft.md")
    text = draft.read_text(encoding="utf-8")
    _file("services.json").write_text(json.dumps([asdict(s) for s in services], indent=2), encoding="utf-8")
    _file("business.md").write_text(text, encoding="utf-8")
    draft.unlink()
    get_knowledge.cache_clear()


def reset() -> list[str]:
    """Reset onboarding: forget the draft, the onboarded document and the services
    table, so the business is onboarded again from the start. Returns what was
    removed, for the page to show. Customers' bookings are not touched."""
    from ..business.store import get_knowledge

    removed = []
    for name, what in (("services.json", "services table"), ("business.md", "onboarded document"),
                       ("draft.md", "documents waiting to go live")):
        if (path := _file(name)).exists():
            path.unlink()
            removed.append(what)
    get_knowledge.cache_clear()
    return removed


def live_document() -> Path | None:
    """The onboarded document, or None before the business has gone live."""
    live = _file("business.md")
    return live if live.exists() else None


def live_services() -> list[dict]:
    """The services table as the owner saved it; empty before going live."""
    saved = _file("services.json")
    return json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else []
