"""Turning text into vectors: Pinecone's hosted embedding model, through LangChain.

LangChain's `Embeddings` interface has two methods: `embed_documents` for
the chunks (when they are stored) and `embed_query` for a question (each
time one is asked). `PineconeEmbeddings` (langchain-pinecone) implements it
with a model that runs on Pinecone's servers: nothing is downloaded, and it
needs only PINECONE_API_KEY, the key the vector store uses.

The model, llama-text-embed-v2, was trained on (question, passage) pairs and
is told which one each text is, so a short question lands near the passage
that answers it; PineconeEmbeddings does that for each method. It can give
vectors of several sizes; 384 numbers keeps the index small.

Tests replace this with LangChain's DeterministicFakeEmbedding (tests/conftest.py):
they check the wiring offline; whether search finds the right passage is
measured by the retrieval eval (evals/retrieval.py).
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_pinecone import PineconeEmbeddings

from ..config import get_settings

MODEL, DIMENSION = "llama-text-embed-v2", 384
MAX_TOKENS = 2048  # the most the model reads of one text; the rest is ignored
# Part of the index signature: a different model or size rebuilds the index.
NAME = f"pinecone/{MODEL}-{DIMENSION}"


@lru_cache  # one client for the app's life
def get_embeddings() -> Embeddings:
    """The embedding model, as a LangChain Embeddings."""
    return PineconeEmbeddings(model=MODEL, dimension=DIMENSION, pinecone_api_key=get_settings().pinecone_api_key)
