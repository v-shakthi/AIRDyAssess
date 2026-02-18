"""
config.py — Centralised settings for the AI Readiness Advisor.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "AI Readiness & Migration Advisor"
    app_version: str = "1.0.0"

    # LLM
    anthropic_api_key: Optional[str] = None
    model: str = "claude-opus-4-6"
    max_tokens: int = 4096

    # Vector store
    chroma_persist_dir: str = "chroma_store"
    collection_name: str = "enterprise_docs"
    chunk_size: int = 1000
    chunk_overlap: int = 150
    top_k_retrieval: int = 8

    # Reports
    reports_dir: str = "reports"

    # API
    api_key: str = "sk-advisor-demo-001"

    class Config:
        env_file = ".env"


settings = Settings()
