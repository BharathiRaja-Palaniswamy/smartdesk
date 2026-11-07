"""Search: finding the passages of the business's documents that answer a question (RAG).

Built from LangChain parts, one file per step, read in this order:

    documents.py     load the document; cut it into chunks (TokenTextSplitter)
    headers.py       write where each chunk sits above it, for search only
    embeddings.py    turn text into vectors (PineconeEmbeddings, hosted)
    vectorstores/    keep the chunks and their vectors (Pinecone; in memory for tests),
                     filled when empty, rebuilt when the document changes
    rerankers.py     reorder the candidates, best first (PineconeRerank, hosted)
    retriever.py     search, rerank, keep the best few (a BaseRetriever)
    errors.py        the one error search raises when Pinecone cannot be reached

Both assistants use the retriever: the Front Desk agent through its
search tool (frontdesk/agent.py), the owner chat in its graph (owner/).

Each part sits behind LangChain's common interface for that kind of
component (Embeddings, VectorStore, BaseDocumentCompressor, BaseRetriever),
so another provider is a change in one file. Only langchain-core and the
standalone packages (langchain-text-splitters, langchain-pinecone) are used:
langchain-community is being retired, so nothing here depends on it.
"""
