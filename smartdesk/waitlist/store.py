"""The waitlist and the offers, as two small JSON files in the business's folder.

    waitlist.json  who is waiting: name, phone, service, day, optional time
                   window, when they agreed to wait, and their status
    offers.json    each slot offered: to whom, which slot, when it expires,
                   and how it ended

Demo build: files, read and written whole under one lock. With cells (M2)
they become tables in the business's database.
"""

import json
import threading
from pathlib import Path
from typing import Any

from ..config import get_settings

_lock = threading.Lock()  # one change at a time: read, change, write


def _path(kind: str) -> Path:
    return get_settings().business_folder / f"{kind}.json"


def load(kind: str) -> list[dict[str, Any]]:
    """Every row of `kind` ("waitlist" or "offers")."""
    path = _path(kind)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def change(kind: str, edit) -> Any:
    """Run `edit(rows)` on the rows of `kind`, under the lock, and save them.
    Returns what `edit` returns."""
    with _lock:
        rows = load(kind)
        result = edit(rows)
        path = _path(kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return result
