"""Settings loaded from .env via pydantic-settings."""

from __future__ import annotations
from pathlib import Path
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2025-01-01-preview"

    # Azure AI Speech
    azure_speech_key: str = ""
    azure_speech_region: str = "swedencentral"

    # Azure OpenAI constraints
    azure_openai_max_tokens: int = 100

    # Legacy OpenAI (offline/test fallback)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Database
    database_url: str = ""
    redis_url: str = ""

    # ElevenLabs (optional — higher quality TTS for voice loop)
    # Free tier only works with voices created in your own account (Voice Design / cloning).
    # Premade library voices (Rachel etc.) require a paid plan.
    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_output_format: str = "pcm_16000"  # pcm_16000 = lowest latency; pcm_22050/pcm_44100 = higher quality

    # Voice
    tts_model_path: str = "./models/galdr_voice"
    stt_model: str = "whisper-1"

    # Performance targets
    max_response_latency_ms: int = 2000
    max_concurrent_sessions: int = 50

    # Reverb post-processing — HOLDOUT until TTFA p95 < 500ms is confirmed.
    # Adds scipy fftconvolve to each spoken sentence before sd.play().
    # Measured cost: ~2-8ms per sentence at 16kHz. Toggle via .env.
    reverb_processing_enabled: bool = False

    @computed_field
    @property
    def use_azure(self) -> bool:
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint)

settings = Settings()
