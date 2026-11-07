"""The one error search raises when a service it needs cannot be reached.

Search uses Pinecone three ways: to store the chunks, to embed text, and to
rerank. Each can fail for reasons outside the app: no network, a bad key, a
plan's limit reached. `reaching` turns every such failure into
ModelUnavailable, so the chat routes catch one error and answer "the
assistant is unavailable" instead of crashing.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import urllib3
from pinecone.exceptions import PineconeException


class ModelUnavailable(RuntimeError):
    """A search service could not be reached. The chat routes turn this into
    "the assistant is unavailable"; the message says why, for the logs."""


@contextmanager
def reaching(service: str) -> Iterator[None]:
    """Run the block, turning a Pinecone or network failure into ModelUnavailable
    that names `service` and says what went wrong."""
    try:
        yield
    except (PineconeException, urllib3.exceptions.HTTPError) as error:
        raise ModelUnavailable(f"{service} could not be reached: {error}") from error
