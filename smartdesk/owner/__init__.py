"""The owner chat, as a LangGraph graph: POST /api/report/chat answers through it.

The owner asks about the business; the model answers from the passages the
retriever finds, and may call the report tool for figures, at most
MAX_TOOL_ROUNDS rounds:

  prompt.py  the prompt template, and the check on what a reply cites
  state.py   what the graph carries from step to step
  nodes.py   the steps: prepare, agent, tools, and the choice after agent
  graph.py   how the steps are joined; the model is reached through smartdesk/models/

Each node is a step of its own in a LangSmith trace when tracing is on.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from ..reports.dataset import Dataset
from .graph import build_graph


@dataclass(frozen=True)
class OwnerAnswer:
    """The graph's reply, and what the route needs to check and label it."""

    reply: BaseModel | None  # an instance of the schema, or None when there was no usable reply
    headings: list[str]  # the headings the model was shown: all a reply may cite
    chunks: int  # how many passages were retrieved
    reports: list[str]  # the reports the model asked for


def answer(instructions: str, question: str, schema: type[BaseModel], dataset: Dataset) -> OwnerAnswer:
    """Answer one owner question by running the graph."""
    state = build_graph(instructions, schema, dataset).invoke({"question": question, "messages": [], "reports": []})
    # No reply when the graph stopped while the model was still asking for
    # tools (it ran out of rounds); the route reports that.
    return OwnerAnswer(reply=state["reply"], headings=state["headings"], chunks=state["chunks"],
                       reports=state["reports"])
