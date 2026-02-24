"""Speech-to-text via Whisper.

Optimised for outdoor use (background noise, wind). Raw audio is never
stored — only the transcript hits the database.
"""

from __future__ import annotations

import io
import logging

from galdr.config import settings

logger = logging.getLogger(__name__)


class STTEngine:
    """Transcribes audio bytes to text using Whisper."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def transcribe(self, audio_data: bytes, language: str = "sv") -> str:
        """Return transcribed text. Empty string if no API key or on error."""
        if not settings.openai_api_key:
            return ""

        try:
            client = await self._get_client()
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.webm"

            transcript = await client.audio.transcriptions.create(
                model=settings.stt_model,
                file=audio_file,
                language=language,
            )
            return transcript.text
        except Exception as e:
            logger.error(f"STT error: {e}")
            return ""
