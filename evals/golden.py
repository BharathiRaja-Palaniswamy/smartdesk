"""The golden dataset: every eval case for one business, in one file.

Each business has its own, kept with that business, never in SmartDesk:
SMARTDESK_EVAL_SET names the file to use.

Each case names its `target`, the part of the app it tests:

  frontdesk   the Front Desk agent: a conversation, played turn by turn (frontdesk.py)
  rag_qa      the customer question-and-answer chat, answered from the guide (chats.py)
  owner_chat  the owner's chat about the business and its figures (chats.py)

and its `split`, the kind of case it is, so a score can be read per kind:

  happy          common requests that should go through
  edge           ambiguous, partial, out of scope, beyond one booking, unsafe
  known_failure  seen failing before; kept so the failure cannot come back
  adversarial    injection, others' data, the owner's figures

A case's `expected` is its label: what must happen, in layers (routing,
extraction, outcome, answer). The runner plays the case and checks each layer
against it; a case passes when every layer does.
"""

import json
from typing import Any

from smartdesk.config import get_settings
TARGETS = ("frontdesk", "rag_qa", "owner_chat")
SPLITS = ("happy", "edge", "known_failure", "adversarial")

Case = dict[str, Any]


def load() -> dict[str, Any]:
    """The whole file: its name, version, notes and cases."""
    path = get_settings().eval_set_path
    if path is None:
        raise SystemExit("No eval set: set SMARTDESK_EVAL_SET to the business's golden set (a JSON file).")
    return json.loads(path.read_text(encoding="utf-8"))


def cases(target: str = "all", only: list[str] | None = None) -> list[Case]:
    """The cases for `target` ("all" for every one), in the file's order; with
    `only`, just the cases whose id starts with one of those texts."""
    chosen = [case for case in load()["cases"] if target in ("all", case["target"])]
    if only:
        chosen = [case for case in chosen if case["id"].startswith(tuple(only))]
    return chosen
