"""
Request models — typed Pydantic schemas for all API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    """A single chat message in history."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Request body for the /api/chat endpoint."""
    message: str = Field(..., min_length=1, max_length=50000, description="User message")
    graph: dict = Field(..., description="React Flow graph JSON with nodes and edges")
    history: Optional[list[ChatMessage]] = Field(default=None, description="Chat history")


class SaveAgentRequest(BaseModel):
    """Request body for saving an agent."""
    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    graph: dict = Field(..., description="Agent graph JSON")
