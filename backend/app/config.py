"""
Centralized configuration — all environment variables and settings in one place.
Uses Pydantic Settings for validation and type safety.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── API Keys ──
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    huggingface_token: str = Field(default="", alias="HUGGINGFACEHUB_API_TOKEN")

    # ── CORS ──
    cors_origins: list[str] = ["*"]

    # ── File Upload ──
    upload_max_size_mb: int = 10
    allowed_extensions: set[str] = {".pdf", ".txt", ".csv", ".md", ".json", ".py", ".js", ".html", ".css", ".log"}

    # ── RAG Settings ──
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Paths ──
    upload_dir: Path = Path(__file__).parent.parent / "uploads"
    vector_dir: Path = Path(__file__).parent.parent / "vector_stores"

    # ── Agent ──
    default_model: str = "llama-3.3-70b-versatile"
    default_temperature: float = 0.7
    default_max_tokens: int = 1024
    recursion_limit: int = 25

    # ── Logging ──
    log_level: str = "INFO"

    model_config = {
        "env_file": os.path.join(Path(__file__).parent.parent, ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(exist_ok=True)
settings.vector_dir.mkdir(exist_ok=True)
