"""Tests for loading and splitting the business document (smartdesk/search/documents.py).

Run with:  .venv/bin/python -m pytest tests/test_search_documents.py
"""

from smartdesk.config import get_settings
from smartdesk.search.documents import load_document, split_document
from smartdesk.search.headers import count_tokens


def test_the_document_loads_as_one_document_with_its_source():
    document = load_document()
    assert document.page_content.startswith("# Test Studio")
    assert document.metadata["source"].endswith("business.md")


def test_chunks_are_numbered_in_order_and_fit_the_chunk_size():
    chunks = split_document(load_document())
    assert [chunk.metadata["id"] for chunk in chunks] == [f"chunk-{n}" for n in range(len(chunks))]
    assert all(count_tokens(chunk.page_content) <= get_settings().chunk_tokens for chunk in chunks)


def test_each_chunk_names_the_headings_it_covers():
    chunks = split_document(load_document())
    assert all(chunk.metadata["sections"] for chunk in chunks)
    cancellation = next(chunk for chunk in chunks if "Late cancellations may incur" in chunk.page_content)
    assert "Cancellation Policy" in cancellation.metadata["sections"]


def test_each_chunk_knows_where_it_starts():
    document = load_document()
    for chunk in split_document(document):
        start = chunk.metadata["start"]
        assert document.page_content[start:start + len(chunk.page_content)] == chunk.page_content
