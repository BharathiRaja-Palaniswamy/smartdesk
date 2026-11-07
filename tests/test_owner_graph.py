"""Tests for the owner chat (smartdesk/owner/), behind POST /api/report/chat.

The model gateway's model is replaced by a stand-in that plays back prepared
messages (tests/standins.py), so these run without an API key and spend
nothing. Search uses the in-memory store and fake embeddings (tests/conftest.py).

Run with:  .venv/bin/python -m pytest tests/test_owner_graph.py
"""

import json

import pytest
from conftest import signed_in
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from standins import use_standin

from smartdesk.app import app
from smartdesk.models.structured import ANSWER as ANSWER_TOOL
from smartdesk.owner import graph, nodes
from smartdesk.owner.routes import INSTRUCTIONS, OwnerReply
from smartdesk.replies import ReplyItem
from smartdesk.reports.dataset import get_dataset
from smartdesk.reports.tools import MAX_TOOL_ROUNDS, TOOL_NAME
from smartdesk.search.errors import ModelUnavailable

ANSWER = OwnerReply(answer="Facials in September 2026.", covered=True,
                    items=[ReplyItem(name="Revenue", detail="$7,530")],
                    insights=["Facials were the second-highest earning category."],
                    sections=["Made-up Section"], suggestions=["One?", "Two?", "Three?", "Four?"])
SEPTEMBER_FACIALS = {"start": "2026-09-01", "end": "2026-09-30", "category": "Facials"}


@pytest.fixture(autouse=True)
def own_store(tmp_path, monkeypatch):
    """Each test searches its own in-memory store, three passages a question."""
    monkeypatch.setenv("SMARTDESK_VECTOR_STORE_PATH", str(tmp_path / "vectors"))
    monkeypatch.setenv("SMARTDESK_RETRIEVAL_TOP_K", "3")


def asks_for_report(call_id: str = "call-1") -> AIMessage:
    """A model message that asks for the September facials report."""
    return AIMessage(content="", tool_calls=[{"name": TOOL_NAME, "args": SEPTEMBER_FACIALS, "id": call_id}])


def answers() -> AIMessage:
    """A model message that gives the structured answer, as JSON text."""
    return AIMessage(content=ANSWER.model_dump_json())


@pytest.fixture
def run(monkeypatch):
    """Runs the graph with a stand-in model that plays back `replies` in order.
    Returns the final state."""
    def run_graph(*replies: AIMessage) -> dict:
        use_standin(monkeypatch, list(replies))
        return graph.build_graph(INSTRUCTIONS, OwnerReply, get_dataset()).invoke(
            {"question": "How did facials do in September?", "messages": [], "reports": []})
    return run_graph


def test_the_graph_runs_the_tool_then_answers(run):
    state = run(asks_for_report(), answers())
    system, question, request, result, reply = state["messages"]
    assert isinstance(system, SystemMessage) and "owner of a business" in system.content
    assert question.content == "How did facials do in September?"
    assert request.tool_calls[0]["args"] == SEPTEMBER_FACIALS
    # The tool's result is tied to the request by id, and holds the real figures.
    assert isinstance(result, ToolMessage) and result.tool_call_id == "call-1"
    report = json.loads(result.content)
    assert report["filters"]["category"] == "Facials" and report["summary"]["revenue"] == 7530
    assert OwnerReply.model_validate_json(reply.text) == ANSWER and state["reply"] == ANSWER
    assert state["reports"] == ["2026-09-01 to 2026-09-30, Facials"] and state["rounds"] == 1


def test_a_profile_question_needs_no_tool(run):
    state = run(answers())
    assert len(state["messages"]) == 3 and state["rounds"] == 0 and state["reports"] == []


def test_the_prompt_holds_only_the_retrieved_passages(run):
    state = run(answers())
    assert state["chunks"] == 3 and state["messages"][0].content.count("<excerpt>\n") == 3


def test_when_the_model_keeps_asking_it_must_answer_once_the_rounds_are_used(run):
    # As seen in the evals: report after report until the rounds ran out, then "could not answer" (503).
    state = run(*[asks_for_report(f"call-{n}") for n in range(MAX_TOOL_ROUNDS)], answers())
    assert state["rounds"] == MAX_TOOL_ROUNDS
    assert state["reply"] == ANSWER  # answered with the reports it had


def test_an_unknown_tool_gets_an_error_result(run):
    unknown = AIMessage(content="", tool_calls=[{"name": "get_weather", "args": {}, "id": "call-1"}])
    state = run(unknown, answers())
    assert "no tool called get_weather" in json.loads(state["messages"][3].content)["error"]


def test_the_graph_takes_the_reply_from_the_answer_call(run):
    # Every model gives the reply by calling an "answer" tool (models/structured.py).
    answer_call = AIMessage(content="", tool_calls=[{"name": ANSWER_TOOL, "args": ANSWER.model_dump(), "id": "a"}])
    state = run(asks_for_report(), answer_call)
    assert state["reply"] == ANSWER and state["reports"] == ["2026-09-01 to 2026-09-30, Facials"]


def test_the_route_answers_through_the_graph(monkeypatch):
    use_standin(monkeypatch, [asks_for_report(), answers()])
    reply = signed_in(app).post("/api/report/chat", json={"question": "How did facials do in September?"}).json()
    # No made-up section is shown, and at most three suggestions.
    assert reply == {"answer": "Facials in September 2026.", "covered": True,
                     "items": [{"name": "Revenue", "detail": "$7,530"}],
                     "insights": ["Facials were the second-highest earning category."],
                     "sections": [], "suggestions": ["One?", "Two?", "Three?"],
                     "chunks": 3, "reports": ["2026-09-01 to 2026-09-30, Facials"]}


def test_the_route_reports_when_the_graph_has_no_answer(monkeypatch):
    use_standin(monkeypatch, [AIMessage(content="Not JSON"), AIMessage(content="Still not JSON")])  # asked twice
    reply = signed_in(app).post("/api/report/chat", json={"question": "Hello"})
    assert reply.status_code == 503


def test_the_route_reports_when_search_cannot_be_reached(monkeypatch):
    class Unreachable:
        def invoke(self, question):
            raise ModelUnavailable("Pinecone search could not be reached: refused")

    monkeypatch.setattr(nodes, "get_retriever", Unreachable)
    reply = signed_in(app).post("/api/report/chat", json={"question": "Hello"})
    assert reply.status_code == 503 and reply.json()["detail"] == "The assistant is unavailable right now."


def test_only_the_owner_may_ask(monkeypatch):
    from fastapi.testclient import TestClient

    assert TestClient(app).post("/api/report/chat", json={"question": "Hello"}).status_code == 401
