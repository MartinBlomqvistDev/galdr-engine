"""Settings and BYOK (Bring Your Own Key) configuration."""

from __future__ import annotations
import os
from pydantic import BaseModel, Field

class Settings(BaseModel):
    """Reads from environment variables or defaults. 
    Simplified for portability across different environments.
    """

    # LLM — BYOK, engine runs offline without it
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = "gpt-4o"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = ""
    redis_url: str = ""

    # Voice
    tts_model_path: str = "./models/galdr_voice"
    stt_model: str = "whisper-1"

    # Performance targets
    max_response_latency_ms: int = 2000
    max_concurrent_sessions: int = 50

settings = Settings()
