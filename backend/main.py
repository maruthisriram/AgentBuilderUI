"""
Agent Builder Backend — FastAPI server
Provides /api/chat endpoint that converts graph JSON → LangGraph agent → streams response.
"""

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from agent_builder import run_agent

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
