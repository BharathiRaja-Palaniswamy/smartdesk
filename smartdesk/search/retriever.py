"""Finding the chunks that best answer a question.

    question -> the store's closest chunks -> (the reranker reorders them) -> the best few

A LangChain retriever is anything that turns a question into documents
(`BaseRetriever`). It is also a "Runnable", so each call is traced in
LangSmith as a retriever step without any extra code.

This one searches the vector store (vectorstores/); with the reranker on
(rerankers.py) it fetches SMARTDESK_RERANK_CANDIDATES chunks and keeps the
best SMARTDESK_RETRIEVAL_TOP_K, so the model is given the same number of
chunks either way.

Chunks are stored with their header above their text (headers.py), and both
the search and the reranker read them that way; the header is taken off
last, so the model is given the chunk's own text.

(LangChain's ContextualCompressionRetriever also does "search, then
rerank", but it lives in the legacy langchain-classic package, and cannot
fetch more candidates than it keeps, which reranking needs.)
"""

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableLambda

from ..config import get_settings
from .errors import reaching
from .headers import without_header
from .rerankers import get_compressor
from .vectorstores import get_vectorstore


class BusinessRetriever(BaseRetriever):
    """Searches the business's documents, reranks, and keeps the best chunks.

    Each document returned has in its metadata: id, sections (a list of
    headings), score (similarity, near 1 is the same meaning) and, when
    reranked, relevance_score.
    """

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        """The chunks that best answer `query`, best first.

        The search and the reranking each run as a step of their own (a
        RunnableLambda), so a LangSmith trace shows both lists: the
        candidates in similarity order, then reordered by the reranker.
        Passing `run_manager.get_child()` as the callbacks records each step
        as a child of this retriever's run.
        """
        settings = get_settings()
        keep = settings.retrieval_top_k
        compressor = get_compressor(keep)
        fetch = max(settings.rerank_candidates, keep) if compressor else keep
        callbacks = {"callbacks": run_manager.get_child()}
        with reaching("Pinecone search"):
            documents = RunnableLambda(search_chunks, name="search").invoke(
                {"query": query, "k": fetch}, config=callbacks)
            if compressor:
                documents = RunnableLambda(
                    lambda step: list(compressor.compress_documents(step["documents"], step["query"])),
                    name="rerank",
                ).invoke({"query": query, "documents": documents}, config=callbacks)
        return [as_found(doc) for doc in documents[:keep]]


def search_chunks(step: dict) -> list[Document]:
    """The `k` chunks closest to `query` in the vector store, best first, each
    still with its header, and its similarity score in metadata."""
    found = get_vectorstore().similarity_search_with_relevance_scores(step["query"], k=step["k"])
    return [doc.model_copy(update={"metadata": {**doc.metadata, "score": score}}) for doc, score in found]


def as_found(doc: Document) -> Document:
    """A chunk as the model is given it: its own text, without the header,
    and its sections as a list (stored as one string, a heading per line)."""
    return doc.model_copy(update={
        "page_content": without_header(doc.page_content, doc.metadata.get("header", "")),
        "metadata": {**doc.metadata, "sections": doc.metadata["sections"].split("\n")},
    })


def get_retriever() -> BusinessRetriever:
    """The retriever, named so its steps are easy to find in a LangSmith trace."""
    return BusinessRetriever(name="business_retriever")
