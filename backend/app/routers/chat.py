"""
Chat router — handles the /api/chat SSE streaming endpoint.
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.requests import ChatRequest
from app.services.graph_compiler import run_agent
from app.utils.logging import get_logger

logger = get_logger("router.chat")

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Receive user message + agent graph JSON.
    Build a LangGraph agent from the graph and stream the response via SSE.
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="Message is required")
    if not request.graph:
        raise HTTPException(status_code=400, detail="Agent graph is required")

    logger.info(f"Chat request: message='{request.message[:50]}...'")

    # Convert ChatMessage models to dicts for history
    history = None
    if request.history:
        history = [{"role": h.role, "content": h.content} for h in request.history]

    async def event_stream():
        try:
            async for event_json in run_agent(
                graph_json=request.graph,
                message=request.message,
                history=history,
            ):
                yield f"data: {event_json}\n\n"
            yield "data: [DONE]\n\n"
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
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
