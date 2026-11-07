"""Tracing with LangSmith: a record of what happened inside each chat question.

A trace is a tree of steps ("runs"). LangChain and LangGraph record their own
steps: a graph's nodes, each model call with its prompt, reply and tokens,
the retriever's search and rerank, each tool and its result. The routes add
`@traceable` above themselves, so the whole request is the top step.

Tracing is switched on by settings in `.env`, read by the langsmith library
itself:

    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=...
    LANGSMITH_PROJECT=smartdesk     the project the traces are filed under

Without them nothing is recorded and the app runs as before.

`setup`, run once when the app starts, sends every trace, from any step,
through one LangSmith client, which masks personal details before sending
(privacy.py) and labels the trace with the code's commit, so a trace can be
traced back to the code that made it. Which project the traces go to is a
setting (LANGSMITH_PROJECT): smartdesk-local on a laptop, smartdesk-prod in
production, smartdesk-evals for the evals (evals/observe.py).
"""

import os
import subprocess

import langsmith
from langsmith.anonymizer import create_anonymizer

from .privacy import mask


def _commit() -> str:
    """The code's git commit, or SMARTDESK_COMMIT where there is no git (some hosts)."""
    try:
        found = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return found.stdout.strip() or os.getenv("SMARTDESK_COMMIT", "unknown")
    except (OSError, subprocess.SubprocessError):
        return os.getenv("SMARTDESK_COMMIT", "unknown")


def setup() -> None:
    """Send every trace through one client that masks personal details, with the
    commit in each trace's metadata. Nothing is sent when tracing is off."""
    if os.getenv("LANGSMITH_TRACING", "").lower() != "true":
        return
    langsmith.configure(client=langsmith.Client(anonymizer=create_anonymizer(mask)),
                        metadata={"commit": _commit()})

