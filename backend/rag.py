"""
RAG Engine — handles file uploads, chunking, embedding, storage, and retrieval.
Uses FAISS for vector storage and HuggingFace for embeddings.
"""

import os
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

# Directory to store uploaded files and vector indices
UPLOAD_DIR = Path(__file__).parent / "uploads"
VECTOR_DIR = Path(__file__).parent / "vector_stores"
UPLOAD_DIR.mkdir(exist_ok=True)
VECTOR_DIR.mkdir(exist_ok=True)

# Singleton embeddings model (loaded once, reused)
_embeddings = None


def get_embeddings():
    """Get or create the embeddings model (local, no API needed)."""
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
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
        # Try loading as text
        loader = TextLoader(file_path, encoding="utf-8")
    return loader.load()


def process_uploaded_file(file_path: str, kb_id: str, original_filename: str) -> dict:
    """
    Process an uploaded file: load → chunk → embed → store in FAISS.
    Returns metadata about the processed file.
    """
    # Step 1: Load document
    try:
        documents = _load_document(file_path)
    except Exception as e:
        return {"error": f"Failed to load {original_filename}: {str(e)}"}

    if not documents:
        return {"error": f"No content found in {original_filename}"}

    # Add source metadata
    for doc in documents:
        doc.metadata["source"] = original_filename

    # Step 2: Split into chunks
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = text_splitter.split_documents(documents)
    except Exception as e:
        return {"error": f"Failed to split {original_filename}: {str(e)}"}

    if not chunks:
        return {"error": f"No text chunks created from {original_filename}"}

    # Step 3: Get embeddings
    try:
        embeddings = get_embeddings()
        # Quick test — embed a small string to verify the API works
        test = embeddings.embed_query("test")
        if not test or len(test) == 0:
            return {"error": "Embeddings API returned empty result. Check your HUGGINGFACEHUB_API_TOKEN."}
    except Exception as e:
        return {"error": f"Embeddings error: {str(e)}. Check your HUGGINGFACEHUB_API_TOKEN in .env"}

    # Step 4: Create or update FAISS index
    try:
        if kb_id in _knowledge_bases:
            _knowledge_bases[kb_id].add_documents(chunks)
        else:
            _knowledge_bases[kb_id] = FAISS.from_documents(chunks, embeddings)
    except Exception as e:
        return {"error": f"FAISS indexing error: {str(e)}"}

    # Step 5: Save to disk
    try:
        index_path = VECTOR_DIR / kb_id
        _knowledge_bases[kb_id].save_local(str(index_path))
    except Exception as e:
        return {"error": f"Failed to save index: {str(e)}"}

    return {
        "success": True,
        "filename": original_filename,
        "chunks": len(chunks),
        "pages": len(documents),
        "kb_id": kb_id,
    }


def query_knowledge_base(kb_id: str, query: str, k: int = 4) -> str:
    """
    Query a knowledge base and return relevant context.
    """
    if kb_id not in _knowledge_bases:
        # Try loading from disk
        index_path = VECTOR_DIR / kb_id
        if index_path.exists():
            embeddings = get_embeddings()
            _knowledge_bases[kb_id] = FAISS.load_local(
                str(index_path), embeddings, allow_dangerous_deserialization=True
            )
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
    # From memory
    kb_ids = set(_knowledge_bases.keys())
    # From disk
    if VECTOR_DIR.exists():
        for p in VECTOR_DIR.iterdir():
            if p.is_dir():
                kb_ids.add(p.name)
    return list(kb_ids)


def delete_knowledge_base(kb_id: str) -> bool:
    """Delete a knowledge base from memory and disk."""
    if kb_id in _knowledge_bases:
        del _knowledge_bases[kb_id]
    index_path = VECTOR_DIR / kb_id
    if index_path.exists():
        shutil.rmtree(index_path)
        return True
    return False


def create_kb_retriever_tool(kb_id: str, kb_name: str = "Knowledge Base"):
    """
    Create a LangChain tool that searches a specific knowledge base.
    This is dynamically created per-agent based on what KB nodes are in the graph.
    """
    # Clean the name for tool calling (only alphanumeric + underscores allowed)
    safe_id = kb_id.replace("-", "_")

    @tool
    def knowledge_base_search(query: str) -> str:
        """Search the knowledge base for relevant information about uploaded documents. Input should be a search query string."""
        return query_knowledge_base(kb_id, query, k=4)

    # Override the name and description to be specific
    knowledge_base_search.name = f"search_{safe_id}"
    knowledge_base_search.description = (
        f"Search the '{kb_name}' knowledge base for relevant information about uploaded documents. "
        f"Use this when the user asks about content from their uploaded files. "
        f"Input should be a search query string."
    )
    return knowledge_base_search
