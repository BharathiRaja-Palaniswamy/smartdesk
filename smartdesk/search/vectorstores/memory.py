"""LangChain's in-memory vector store, for tests and working offline.

`InMemoryVectorStore` ships with langchain-core: no database, no extra
package, no key. It lives in this process, so it starts empty when the app
starts and is filled then. Used by the tests (so they never touch a hosted
store) and for working offline: SMARTDESK_VECTOR_STORE=memory.

One store is kept per store folder setting and signature: a changed document
gets a new, empty store, and each test, which sets its own folder, its own.
"""

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore, VectorStore

from ...config import get_settings


class MemoryVectorStore(InMemoryVectorStore):
    """InMemoryVectorStore, with its relevance scores defined: its search
    already scores by cosine similarity, so the score is used as it is."""

    def _select_relevance_score_fn(self):
        return lambda similarity: similarity


# (store folder, signature) -> its store, kept for every question, or it would start empty each time.
_stores: dict[tuple[str, str], MemoryVectorStore] = {}


def make_memory(embeddings: Embeddings, signature: str) -> tuple[VectorStore, bool]:
    """The store for `signature`, and whether it already holds the chunks."""
    key = (str(get_settings().vector_store_path), signature)
    store = _stores.setdefault(key, MemoryVectorStore(embedding=embeddings))
    return store, bool(store.store)  # `store.store` holds the chunks, by id
