"""
Agents router — handles /api/agents/* endpoints for saving/loading agent graphs.
"""

from fastapi import APIRouter, HTTPException

from app.models.requests import SaveAgentRequest
from app.utils.logging import get_logger

logger = get_logger("router.agents")

router = APIRouter(prefix="/api", tags=["agents"])

# In-memory agent storage (in production, use a database)
saved_agents = {}


@router.post("/save-agent")
async def save_agent(request: SaveAgentRequest):
    """Save an agent graph definition."""
    saved_agents[request.name] = request.graph
    logger.info(f"Saved agent: {request.name}")
    return {"status": "saved", "name": request.name}


@router.get("/agents")
async def list_agents():
    """List all saved agents."""
    return {"agents": list(saved_agents.keys())}


@router.get("/agents/{name}")
async def get_agent(name: str):
    """Get a saved agent by name."""
    if name not in saved_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"name": name, "graph": saved_agents[name]}
