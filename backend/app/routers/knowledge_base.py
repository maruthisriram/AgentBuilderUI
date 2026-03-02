"""
Knowledge Base router — handles /api/kb/* endpoints for RAG file uploads.
"""

import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.config import settings
from app.services.rag_engine import (
    process_uploaded_file,
    list_knowledge_bases,
    get_kb_info,
    delete_knowledge_base,
)
from app.utils.logging import get_logger

logger = get_logger("router.kb")

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


@router.post("/upload")
async def upload_to_knowledge_base(
    file: UploadFile = File(...),
    kb_id: str = Form(None),
):
    """
    Upload a file to a knowledge base.
    If kb_id is not provided, a new knowledge base is created.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(settings.allowed_extensions)}"
        )

    # Check file size
    content = await file.read()
    if len(content) > settings.upload_max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.upload_max_size_mb}MB"
        )

    # Generate kb_id if not provided
    if not kb_id:
        kb_id = f"kb-{uuid.uuid4().hex[:8]}"

    logger.info(f"Uploading '{file.filename}' to KB '{kb_id}' ({len(content)} bytes)")

    # Save uploaded file to disk
    kb_upload_dir = settings.upload_dir / kb_id
    kb_upload_dir.mkdir(exist_ok=True)
    file_path = kb_upload_dir / file.filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Process file: load → chunk → embed → store
    result = process_uploaded_file(str(file_path), kb_id, file.filename)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/list")
async def list_kbs():
    """List all knowledge bases."""
    kb_ids = list_knowledge_bases()
    kbs = []
    for kb_id in kb_ids:
        info = get_kb_info(kb_id)
        kbs.append(info or {"kb_id": kb_id, "num_documents": 0})
    return {"knowledge_bases": kbs}


@router.get("/{kb_id}")
async def get_kb(kb_id: str):
    """Get info about a specific knowledge base."""
    info = get_kb_info(kb_id)
    if not info:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    kb_upload_dir = settings.upload_dir / kb_id
    files = []
    if kb_upload_dir.exists():
        files = [f.name for f in kb_upload_dir.iterdir() if f.is_file()]

    return {**info, "files": files}


@router.delete("/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a knowledge base and its files."""
    deleted = delete_knowledge_base(kb_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    logger.info(f"Deleted KB '{kb_id}'")
    return {"status": "deleted", "kb_id": kb_id}
