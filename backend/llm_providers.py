"""
LLM Provider Factory — returns the right LLM instance based on node config.
Uses Groq as the primary provider.
"""

import os
from langchain_groq import ChatGroq


def get_llm(model: str, temperature: float = 0.7, max_tokens: int = 1024):
    """Return a ChatGroq LLM instance for the given model."""
    return ChatGroq(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    )


# Mapping of tool-definition IDs → Groq model strings
MODEL_MAP = {
    "llm-llama33-70b": "llama-3.3-70b-versatile",
    "llm-llama31-8b": "llama-3.1-8b-instant",
    "llm-gemma2": "gemma2-9b-it",
    "llm-compound": "groq/compound",
    "llm-gpt-oss-120b": "openai/gpt-oss-120b",
}
