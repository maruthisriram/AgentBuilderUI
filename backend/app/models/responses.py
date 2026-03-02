"""
Response models — typed Pydantic schemas for API responses.
"""

from pydantic import BaseModel
from typing import Optional


class HealthResponse(BaseModel):
    status: str
    service: str


class UploadResponse(BaseModel):
    success: bool
    filename: str
    chunks: int
    pages: int
    kb_id: str


class KBInfoResponse(BaseModel):
    kb_id: str
    num_documents: int
    files: Optional[list[str]] = None


class KBListResponse(BaseModel):
    knowledge_bases: list[dict]


class DeleteResponse(BaseModel):
    status: str
    kb_id: str


class SaveAgentResponse(BaseModel):
    status: str
    name: str


class AgentListResponse(BaseModel):
    agents: list[str]


class AgentResponse(BaseModel):
    name: str
    graph: dict


class ErrorResponse(BaseModel):
    detail: str
