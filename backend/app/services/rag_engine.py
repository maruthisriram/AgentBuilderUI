"""
RAG Engine — handles file uploads, chunking, embedding, storage, and retrieval.
Uses FAISS for vector storage and HuggingFace for embeddings.
"""

import shutil
import hashlib
from pathlib import Path
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    CSVLoader,
)
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("rag")

# Singleton embeddings model (loaded once, reused)
_embeddings = None


def get_embeddings():
    """Get or create the embeddings model (local, no API needed)."""
    global _embeddings
    if _embeddings is None:
        logger.info(f"Loading embeddings model: {settings.embedding_model}")
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
        )
        logger.info("Embeddings model loaded successfully")
    return _embeddings


# In-memory registry: kb_id → FAISS vectorstore
_knowledge_bases = {}


def _get_file_hash(file_path: str) -> str:
    """Generate a hash for a file to detect duplicates."""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:12]


def _load_document(file_path: str):
    """Load a document based on its extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".csv":
        loader = CSVLoader(file_path)
    elif ext in [".txt", ".md", ".log", ".json", ".py", ".js", ".html", ".css"]:
        loader = TextLoader(file_path, encoding="utf-8")
    else:
        loader = TextLoader(file_path, encoding="utf-8")
    return loader.load()


def process_uploaded_file(file_path: str, kb_id: str, original_filename: str) -> dict:
    """
    Process an uploaded file: load → chunk → embed → store in FAISS.
    Returns metadata about the processed file.
    """
    # Step 1: Load document
    try:
        logger.info(f"Loading document: {original_filename}")
        documents = _load_document(file_path)
    except Exception as e:
        logger.error(f"Failed to load {original_filename}: {e}")
        return {"error": f"Failed to load {original_filename}: {str(e)}"}

    if not documents:
        return {"error": f"No content found in {original_filename}"}

    # Add source metadata
    for doc in documents:
        doc.metadata["source"] = original_filename

    # Step 2: Split into chunks
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = text_splitter.split_documents(documents)
        logger.info(f"Split {original_filename} into {len(chunks)} chunks")
    except Exception as e:
        logger.error(f"Failed to split {original_filename}: {e}")
        return {"error": f"Failed to split {original_filename}: {str(e)}"}

    if not chunks:
        return {"error": f"No text chunks created from {original_filename}"}

    # Step 3: Get embeddings
    try:
        embeddings = get_embeddings()
        test = embeddings.embed_query("test")
        if not test or len(test) == 0:
            return {"error": "Embeddings API returned empty result. Check your HUGGINGFACEHUB_API_TOKEN."}
    except Exception as e:
        logger.error(f"Embeddings error: {e}")
        return {"error": f"Embeddings error: {str(e)}. Check your HUGGINGFACEHUB_API_TOKEN in .env"}

    # Step 4: Create or update FAISS index
    try:
        if kb_id in _knowledge_bases:
            _knowledge_bases[kb_id].add_documents(chunks)
        else:
            _knowledge_bases[kb_id] = FAISS.from_documents(chunks, embeddings)
        logger.info(f"Indexed {len(chunks)} chunks into KB '{kb_id}'")
    except Exception as e:
        logger.error(f"FAISS indexing error: {e}")
        return {"error": f"FAISS indexing error: {str(e)}"}

    # Step 5: Save to disk
    try:
        index_path = settings.vector_dir / kb_id
        _knowledge_bases[kb_id].save_local(str(index_path))
    except Exception as e:
        logger.error(f"Failed to save index: {e}")
        return {"error": f"Failed to save index: {str(e)}"}

    return {
        "success": True,
        "filename": original_filename,
        "chunks": len(chunks),
        "pages": len(documents),
        "kb_id": kb_id,
    }


def query_knowledge_base(kb_id: str, query: str, k: int = 4) -> str:
    """Query a knowledge base and return relevant context."""
    if kb_id not in _knowledge_bases:
        index_path = settings.vector_dir / kb_id
        if index_path.exists():
            embeddings = get_embeddings()
            _knowledge_bases[kb_id] = FAISS.load_local(
                str(index_path), embeddings, allow_dangerous_deserialization=True
            )
            logger.info(f"Loaded KB '{kb_id}' from disk")
        else:
            return f"Knowledge base '{kb_id}' not found. No documents have been uploaded."

    vectorstore = _knowledge_bases[kb_id]
    results = vectorstore.similarity_search(query, k=k)

    if not results:
        return f"No relevant information found for: {query}"

    output = []
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "")
        page_str = f" (page {page + 1})" if page != "" else ""
        output.append(f"**[{i}] {source}{page_str}:**\n{doc.page_content}")

    return "\n\n---\n\n".join(output)


def get_kb_info(kb_id: str) -> Optional[dict]:
    """Get info about a knowledge base."""
    if kb_id in _knowledge_bases:
        vs = _knowledge_bases[kb_id]
        return {
            "kb_id": kb_id,
            "num_documents": vs.index.ntotal if hasattr(vs, "index") else 0,
        }
    return None


def list_knowledge_bases() -> List[str]:
    """List all available knowledge base IDs."""
    kb_ids = set(_knowledge_bases.keys())
    if settings.vector_dir.exists():
        for p in settings.vector_dir.iterdir():
            if p.is_dir():
                kb_ids.add(p.name)
    return list(kb_ids)


def delete_knowledge_base(kb_id: str) -> bool:
    """Delete a knowledge base from memory and disk."""
    if kb_id in _knowledge_bases:
        del _knowledge_bases[kb_id]
    index_path = settings.vector_dir / kb_id
    if index_path.exists():
        shutil.rmtree(index_path)
        logger.info(f"Deleted KB '{kb_id}'")
        return True
    return False


def create_kb_retriever_tool(kb_id: str, kb_name: str = "Knowledge Base"):
    """
    Create a LangChain tool that searches a specific knowledge base.
    Dynamically created per-agent based on what KB nodes are in the graph.
    """
    safe_id = kb_id.replace("-", "_")

    @tool
    def knowledge_base_search(query: str) -> str:
        """Search the knowledge base for relevant information about uploaded documents. Input should be a search query string."""
        return query_knowledge_base(kb_id, query, k=4)

    knowledge_base_search.name = f"search_{safe_id}"
    knowledge_base_search.description = (
        f"Search the '{kb_name}' knowledge base for relevant information about uploaded documents. "
        f"Use this when the user asks about content from their uploaded files. "
        f"Input should be a search query string."
    )
    return knowledge_base_search
