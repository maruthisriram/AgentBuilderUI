"""
Agent Builder Backend — FastAPI Application
Main entry point with lifespan, middleware, and router registration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logging import setup_logging, get_logger
from app.routers import chat, knowledge_base, agents

# Initialize logging
setup_logging(settings.log_level)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    logger.info("=" * 50)
    logger.info("Agent Builder API starting up")
    logger.info(f"CORS origins: {settings.cors_origins}")
    logger.info(f"Upload dir: {settings.upload_dir}")
    logger.info(f"Vector dir: {settings.vector_dir}")

    # Validate critical config
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set — LLM calls will fail")
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set — web search will fail")

    logger.info("Agent Builder API ready")
    logger.info("=" * 50)
    yield
    logger.info("Agent Builder API shutting down")


# Create FastAPI app
app = FastAPI(
    title="Agent Builder API",
    description="Backend for the Agent Builder App — converts visual agent graphs into executable LangGraph agents.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router)
app.include_router(knowledge_base.router)
app.include_router(agents.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Agent Builder API", "version": "2.0.0"}
