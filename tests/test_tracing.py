"""Tests for tracing (smartdesk/tracing.py). Nothing is sent to LangSmith:
tests/conftest.py switches tracing off. What a trace records is LangChain's
own (model calls, graph nodes, the retriever), so only the switch is tested
here; the masking of personal details is tested in test_privacy.py.

Run with:  .venv/bin/pytest tests/test_tracing.py
"""

from langsmith.utils import tracing_is_enabled


def test_tracing_is_off_during_tests():
    assert not tracing_is_enabled()
