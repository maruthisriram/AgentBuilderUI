"""
Agent Builder Backend — FastAPI server
Provides /api/chat endpoint that converts graph JSON → LangGraph agent → streams response.
Also provides /api/kb endpoints for knowledge base (RAG) file uploads.
"""

import os
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

from agent_builder import run_agent
from rag import (
    process_uploaded_file,
    list_knowledge_bases,
    get_kb_info,
    delete_knowledge_base,
    UPLOAD_DIR,
)

app = FastAPI(
    title="Agent Builder API",
    description="Backend for the Agent Builder App — converts visual agent graphs into executable LangGraph agents.",
    version="1.0.0",
)

# CORS — allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    graph: dict
    history: Optional[list] = None


class SaveAgentRequest(BaseModel):
    name: str
    graph: dict


# In-memory agent storage (in production, use a database)
saved_agents = {}


@app.get("/")
async def root():
    return {"status": "ok", "service": "Agent Builder API"}


# ──────────────────────────────────────────────
#  Chat endpoint
# ──────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Receive user message + agent graph JSON.
    Build a LangGraph agent from the graph and stream the response via SSE.
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is required")
    if not request.graph:
        raise HTTPException(status_code=400, detail="Agent graph is required")

    async def event_stream():
        try:
            async for event_json in run_agent(
                graph_json=request.graph,
                message=request.message,
                history=request.history,
            ):
                yield f"data: {event_json}\n\n"
            yield "data: [DONE]\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'Agent execution failed: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────
#  Knowledge Base (RAG) endpoints
# ──────────────────────────────────────────────

@app.post("/api/kb/upload")
async def upload_to_knowledge_base(
    file: UploadFile = File(...),
    kb_id: str = Form(None),
):
    """
    Upload a file to a knowledge base.
    If kb_id is not provided, a new knowledge base is created.
    Supported formats: PDF, TXT, CSV, MD, JSON, PY, JS, HTML, CSS
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file extension
    allowed_extensions = {".pdf", ".txt", ".csv", ".md", ".json", ".py", ".js", ".html", ".css", ".log"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    # Generate kb_id if not provided
    if not kb_id:
        kb_id = f"kb-{uuid.uuid4().hex[:8]}"

    # Save uploaded file to disk
    kb_upload_dir = UPLOAD_DIR / kb_id
    kb_upload_dir.mkdir(exist_ok=True)
    file_path = kb_upload_dir / file.filename

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Process file: load → chunk → embed → store
    result = process_uploaded_file(str(file_path), kb_id, file.filename)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.get("/api/kb/list")
async def list_kbs():
    """List all knowledge bases."""
    kb_ids = list_knowledge_bases()
    kbs = []
    for kb_id in kb_ids:
        info = get_kb_info(kb_id)
        kbs.append(info or {"kb_id": kb_id, "num_documents": 0})
    return {"knowledge_bases": kbs}


@app.get("/api/kb/{kb_id}")
async def get_kb(kb_id: str):
    """Get info about a specific knowledge base."""
    info = get_kb_info(kb_id)
    if not info:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Also list uploaded files
    kb_upload_dir = UPLOAD_DIR / kb_id
    files = []
    if kb_upload_dir.exists():
        files = [f.name for f in kb_upload_dir.iterdir() if f.is_file()]

    return {**info, "files": files}


@app.delete("/api/kb/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a knowledge base and its files."""
    deleted = delete_knowledge_base(kb_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"status": "deleted", "kb_id": kb_id}


# ──────────────────────────────────────────────
#  Agent save/load endpoints
# ──────────────────────────────────────────────

@app.post("/api/save-agent")
async def save_agent(request: SaveAgentRequest):
    """Save an agent graph definition."""
    saved_agents[request.name] = request.graph
    return {"status": "saved", "name": request.name}


@app.get("/api/agents")
async def list_agents():
    """List all saved agents."""
    return {"agents": list(saved_agents.keys())}


@app.get("/api/agents/{name}")
async def get_agent(name: str):
    """Get a saved agent by name."""
    if name not in saved_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"name": name, "graph": saved_agents[name]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
