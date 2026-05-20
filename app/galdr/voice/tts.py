"""Text-to-speech with voice morphing support.

PoC uses OpenAI TTS as a placeholder. In production this gets replaced by
the custom neural model trained on the voice actor's recordings (dcbelle, ~80h).
The VoiceParams → voice mapping here is where that swap happens.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from galdr.config import settings
from galdr.core.nodes import VoiceParams

logger = logging.getLogger(__name__)


class TTSEngine:
    """Synthesizes speech from text using VoiceParams from the node definition."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def synthesize(self, text: str, voice_params: VoiceParams | None = None) -> bytes:
        """Return synthesized audio as opus bytes. Empty bytes if no API key."""
        if not settings.openai_api_key:
            return b""

        params = voice_params or VoiceParams()
        voice = self._map_voice(params)

        try:
            client = await self._get_client()
            response = await client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=params.tempo,
                response_format="opus",
            )
            return response.content
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return b""

    async def synthesize_stream(
        self,
        text: str,
        voice_params: VoiceParams | None = None,
    ) -> AsyncIterator[bytes]:
        """Stream audio chunks — target: first chunk under 500ms."""
        if not settings.openai_api_key:
            return

        params = voice_params or VoiceParams()
        voice = self._map_voice(params)

        try:
            client = await self._get_client()
            async with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=params.tempo,
                response_format="opus",
            ) as response:
                async for chunk in response.iter_bytes(chunk_size=4096):
                    yield chunk
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")

    def _map_voice(self, params: VoiceParams) -> str:
        """Map GALDR VoiceParams to an available TTS voice.

        This is the integration point for the custom neural model in production.
        For the PoC, OpenAI voices are close enough to validate the flow.
        """
        if params.style == "whisper" or params.emotion == "whisper":
            return "shimmer"
        elif params.emotion in ("authoritative", "threatening"):
            return "onyx"
        elif params.emotion == "warm":
            return "nova"
        elif params.pitch_shift > 0.3:
            return "alloy"
        elif params.pitch_shift < -0.3:
            return "echo"
        else:
            return "fable"  # default narrator voice
