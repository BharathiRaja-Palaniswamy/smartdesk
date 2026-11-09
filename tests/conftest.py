"""Set-up shared by every test file. pytest loads this before any test runs.

These are set before the app reads `.env`, so they win over whatever the
developer's `.env` says (load_dotenv never replaces a variable already set):

- Tracing is off: a test run should not send traces to LangSmith.
- The API key is a fake one: tests replace the model with stand-ins, and if
  one ever reached the real API it would be refused instead of spending
  tokens.
- The model gateway uses the Claude set with its default models and no
  fallback, whatever `.env` says, so a test never reaches another provider.
- Search never touches Pinecone: the vector store is LangChain's in-memory
  one, there is no reranker, and the embeddings are LangChain's
  DeterministicFakeEmbedding (the `fake_embeddings` fixture below). Tests
  check search's wiring; whether it finds the right passage is measured by
  the retrieval eval (evals/retrieval.py).
- The business is a made-up test business (tests/fixtures/): its document,
  a year of sample bookings and a small golden eval set. SmartDesk holds no real business's data; tests
  never depend on one.
- There is no Google key, so a test can never reach the real calendars; the
  booking tests use a stand-in calendar (standin_calendar.py).
- Debug mode is off, so replies have their usual shape; the debug test
  turns it on itself.
- The owner's password is a known test one; `signed_in()` gives a test
  browser that has signed in with it, for the owner's pages and data.
"""

import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-a-real-one"
os.environ["PINECONE_API_KEY"] = ""
os.environ["SMARTDESK_MODELS"] = "claude"
os.environ["SMARTDESK_CLAUDE_HIGH"] = "anthropic:claude-opus-5-5"
os.environ["SMARTDESK_CLAUDE_LOW"] = "anthropic:claude-haiku-4-5-20251001"
os.environ["SMARTDESK_MODEL_FALLBACK"] = ""
os.environ["SMARTDESK_VECTOR_STORE"] = "memory"
os.environ["SMARTDESK_RERANKER"] = "none"
os.environ["SMARTDESK_DEBUG"] = "false"
os.environ["SMARTDESK_OWNER_PASSWORD"] = "test-owner-password"
os.environ["SMARTDESK_SESSION_SECRET"] = "test-session-secret"
os.environ["GOOGLE_SERVICE_ACCOUNT"] = ""
os.environ["SMARTDESK_DATA"] = str(FIXTURES / "business.md")
os.environ["SMARTDESK_REPORT_DATA"] = str(FIXTURES / "bookings.json")
os.environ["SMARTDESK_EVAL_SET"] = str(FIXTURES / "golden.json")


@pytest.fixture(autouse=True)
def own_business_folder(tmp_path, monkeypatch):
    """Every test keeps the business's files (onboarded document, waitlist,
    offers) in an empty temporary folder: a business onboarded on this machine
    never reaches a test, and a test never writes into the project. The parsed
    document is forgotten before and after, so none is carried between folders."""
    from smartdesk.business.store import get_knowledge

    monkeypatch.setenv("SMARTDESK_BUSINESS_FOLDER", str(tmp_path / "business"))
    get_knowledge.cache_clear()
    yield
    get_knowledge.cache_clear()


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    """Every test embeds with LangChain's DeterministicFakeEmbedding: the same
    text always gives the same vector, with no model and no network."""
    from langchain_core.embeddings import DeterministicFakeEmbedding

    from smartdesk.search import embeddings, vectorstores

    fake = DeterministicFakeEmbedding(size=embeddings.DIMENSION)
    monkeypatch.setattr(embeddings, "get_embeddings", lambda: fake)
    monkeypatch.setattr(vectorstores, "get_embeddings", lambda: fake)


def signed_in(app):
    """A test browser for `app` that has signed in as the owner."""
    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.post("/api/login", json={"password": os.environ["SMARTDESK_OWNER_PASSWORD"]}).raise_for_status()
    return client
