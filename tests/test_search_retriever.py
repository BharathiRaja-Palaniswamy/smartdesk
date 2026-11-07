"""Tests for finding the chunks for a question (smartdesk/search/retriever.py, rerankers.py).

The reranker is any LangChain document compressor: one test plugs in a fake
one to show the rule (fetch the candidates, reorder, keep the best few). The
embeddings are LangChain's fake ones (tests/conftest.py), so these check the
retriever's steps, not which chunk is best for a question.

Run with:  .venv/bin/python -m pytest tests/test_search_retriever.py
"""

from collections.abc import Sequence

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_pinecone import PineconeRerank
from pinecone.exceptions import PineconeException

from smartdesk.search import retriever as retriever_module
from smartdesk.search.errors import ModelUnavailable, reaching
from smartdesk.search.rerankers import get_compressor
from smartdesk.search.retriever import get_retriever

QUESTION = "What time is Restorative Yoga on Sunday?"


class LongestFirst(BaseDocumentCompressor):
    """A fake reranker: the longer the chunk, the better its score. Keeps `keep`."""

    keep: int

    def compress_documents(self, documents: Sequence[Document], query: str, callbacks=None) -> Sequence[Document]:
        scored = [doc.model_copy(update={"metadata": {**doc.metadata, "relevance_score": float(len(doc.page_content))}})
                  for doc in documents]
        return sorted(scored, key=lambda doc: doc.metadata["relevance_score"], reverse=True)[:self.keep]


@pytest.fixture(autouse=True)
def empty_store(tmp_path, monkeypatch):
    """Each test gets its own store and known settings."""
    monkeypatch.setenv("SMARTDESK_VECTOR_STORE_PATH", str(tmp_path / "vectors"))
    monkeypatch.setenv("SMARTDESK_RETRIEVAL_TOP_K", "7")
    monkeypatch.setenv("SMARTDESK_RERANK_CANDIDATES", "20")


@pytest.fixture
def longest_first(monkeypatch):
    monkeypatch.setattr(retriever_module, "get_compressor", lambda keep: LongestFirst(keep=keep))


def test_documents_carry_their_sections_and_scores():
    documents = get_retriever().invoke(QUESTION)
    assert len(documents) == 7
    assert all(isinstance(doc.metadata["sections"], list) for doc in documents)
    assert all("score" in doc.metadata for doc in documents)


def test_any_reranker_can_be_plugged_in(longest_first):
    documents = get_retriever().invoke(QUESTION)
    assert len(documents) == 7  # SMARTDESK_RETRIEVAL_TOP_K, not the 20 candidates
    scores = [doc.metadata["relevance_score"] for doc in documents]
    assert scores == sorted(scores, reverse=True)


class StepNames(BaseCallbackHandler):
    """Records each step LangChain runs, with what it returned, as a trace would."""

    def __init__(self):
        self.steps = {}

    def on_chain_start(self, serialized, inputs, *, run_id, name=None, **kwargs):
        self.steps[run_id] = {"name": name}

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self.steps[run_id]["output"] = outputs

    def outputs(self, name):
        return next(step["output"] for step in self.steps.values() if step["name"] == name)


def test_the_search_and_the_reranking_are_traced_as_steps(longest_first):
    recorder = StepNames()
    get_retriever().invoke(QUESTION, config={"callbacks": [recorder]})
    searched, reranked = recorder.outputs("search"), recorder.outputs("rerank")
    # The search fetches the 20 candidates; the reranker reorders them and keeps the best 7.
    assert len(searched) == 20 and len(reranked) == 7
    assert {d.metadata["id"] for d in reranked} <= {d.metadata["id"] for d in searched}


def test_the_reranker_reads_each_chunk_with_its_header(monkeypatch):
    seen = []

    class Recorder(LongestFirst):
        def compress_documents(self, documents, query, callbacks=None):
            seen.extend(documents)
            return super().compress_documents(documents, query, callbacks)

    monkeypatch.setattr(retriever_module, "get_compressor", lambda keep: Recorder(keep=keep))
    found = get_retriever().invoke(QUESTION)
    # Header first, as it was embedded; taken off before the model sees the chunk.
    assert all(doc.page_content.startswith(doc.metadata["header"] + "\n") for doc in seen)
    assert all(not doc.page_content.startswith(doc.metadata["header"] + "\n") for doc in found)


def test_the_reranker_setting(monkeypatch):
    monkeypatch.setenv("SMARTDESK_RERANKER", "none")
    assert get_compressor(7) is None
    monkeypatch.setenv("SMARTDESK_RERANKER", "pinecone")
    monkeypatch.setenv("PINECONE_API_KEY", "test-key-not-a-real-one")
    compressor = get_compressor(7)
    assert isinstance(compressor, PineconeRerank) and compressor.top_n == 7
    monkeypatch.setenv("SMARTDESK_RERANKER", "nope")
    with pytest.raises(ValueError, match="Unknown SMARTDESK_RERANKER"):
        get_compressor(7)


def test_a_pinecone_failure_becomes_model_unavailable():
    with pytest.raises(ModelUnavailable, match="Pinecone search could not be reached"):
        with reaching("Pinecone search"):
            raise PineconeException("refused")
