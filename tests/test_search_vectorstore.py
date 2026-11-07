"""Tests for keeping the chunks in a vector store (smartdesk/search/vectorstores/).

The store is pluggable, so keeping the index up to date must work through
LangChain's common VectorStore interface alone: one test plugs in LangChain's
in-memory store to show that. Each test gets its own empty store. The
embeddings are LangChain's fake ones (tests/conftest.py), so these check how
chunks are stored and kept up to date, not what a search finds.

Run with:  .venv/bin/python -m pytest tests/test_search_vectorstore.py
"""

import pytest
from langchain_core.vectorstores import InMemoryVectorStore

from smartdesk.search import vectorstores
from smartdesk.search.documents import load_document, split_document
from smartdesk.search.vectorstores import get_vectorstore


@pytest.fixture(autouse=True)
def empty_store(tmp_path, monkeypatch):
    """Each test gets its own store, away from the app's real one."""
    monkeypatch.setenv("SMARTDESK_VECTOR_STORE_PATH", str(tmp_path / "vectors"))


def chunk_count() -> int:
    return len(split_document(load_document()))


def test_the_index_is_built_once_and_then_reused():
    store = get_vectorstore()
    assert len(store.store) == chunk_count()  # one entry per chunk
    assert get_vectorstore() is store  # nothing changed: the same filled store, not rebuilt


def test_chunks_are_stored_with_their_header_above_their_text():
    stored = next(iter(get_vectorstore().store.values()))
    header = stored["metadata"]["header"]
    assert stored["text"].startswith(f"{header}\n")
    assert isinstance(stored["metadata"]["sections"], str)  # a heading per line: stores keep text, not lists


def test_an_edit_to_the_document_rebuilds_the_index(tmp_path, monkeypatch):
    document = tmp_path / "business_doc.md"
    document.write_text("## Parking\n\nThere is free bicycle parking behind the building.\n", encoding="utf-8")
    monkeypatch.setenv("SMARTDESK_DATA", str(document))
    first = get_vectorstore()
    assert len(first.store) == 1

    document.write_text(document.read_text(encoding="utf-8") + "\n## Bikes\n\nBring a lock.\n", encoding="utf-8")
    second = get_vectorstore()
    assert second is not first  # a new signature: a new store, filled from the edited document
    assert any("Bring a lock." in entry["text"] for entry in second.store.values())


def test_any_langchain_store_can_be_plugged_in(monkeypatch):
    # A store provider returns the store for a signature and whether it is
    # already filled. This one is shared across calls, as a real database would be.
    shared = {}

    def plugged(embeddings, signature):
        store = shared.setdefault(signature, InMemoryVectorStore(embedding=embeddings))
        return store, bool(store.store)

    monkeypatch.setitem(vectorstores.PROVIDERS, "plugged", plugged)
    monkeypatch.setenv("SMARTDESK_VECTOR_STORE", "plugged")
    store = get_vectorstore()
    assert len(store.store) == chunk_count()

    # The store lost its chunks (say it was wiped): the next call fills it again.
    store.delete(ids=list(store.store))
    assert len(get_vectorstore().store) == chunk_count()


def test_an_unknown_store_is_reported(monkeypatch):
    monkeypatch.setenv("SMARTDESK_VECTOR_STORE", "nope")
    with pytest.raises(ValueError, match="Unknown vector store"):
        get_vectorstore()
