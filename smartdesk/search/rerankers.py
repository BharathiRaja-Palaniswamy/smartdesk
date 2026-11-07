"""Reordering the chunks found, best answer first: Pinecone's hosted reranker, through LangChain.

The first search compares vectors, which is fast but rough. A reranker
reads the question and each chunk together and scores how well the chunk
answers it, which is slower but sharper; so the search fetches a few more
chunks than needed, and the reranker picks the best of them.

LangChain calls a reranker a "document compressor": anything that takes the
documents found and the question and returns them reordered
(`BaseDocumentCompressor`). `PineconeRerank` (langchain-pinecone) is one,
running bge-reranker-v2-m3 on Pinecone's servers; it puts each document's
score in metadata["relevance_score"].

SMARTDESK_RERANKER chooses it: "pinecone" (the default) or "none" for no
reranking, which the tests use.
"""

from langchain_core.documents import BaseDocumentCompressor
from langchain_pinecone import PineconeRerank

from ..config import get_settings

MODEL = "bge-reranker-v2-m3"
OFF = "none"


def get_compressor(keep: int) -> BaseDocumentCompressor | None:
    """The reranker, keeping the best `keep` documents, or None when it is off."""
    settings = get_settings()
    if settings.reranker == OFF:
        return None
    if settings.reranker != "pinecone":
        raise ValueError(f"Unknown SMARTDESK_RERANKER: {settings.reranker!r}. Choose pinecone or {OFF}.")
    return PineconeRerank(model=MODEL, top_n=keep, pinecone_api_key=settings.pinecone_api_key)
