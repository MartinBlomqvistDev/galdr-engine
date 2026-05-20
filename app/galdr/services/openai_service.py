import logging
from typing import Any
from openai import AsyncOpenAI
from galdr.services.interfaces import LLMService, TTSService, STTService, VoiceParams
from galdr.config import settings

logger = logging.getLogger(__name__)

class OpenAIService(LLMService, TTSService, STTService):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_text(self, messages: list[dict[str, str]], **kwargs) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=kwargs.get("model", self.model),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 500),
                temperature=kwargs.get("temperature", 0.8),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI LLM error: {e}")
            raise

    async def synthesize(self, text: str, params: VoiceParams) -> bytes:
        # Map narrative parameters to available OpenAI TTS voices.
        # Reverb is currently simulated via speech tempo scaling as a placeholder
        # for custom neural voice model integration.
        try:
            voice_map = {
                "narrator": "onyx",
                "mystic": "shimmer",
                "aggressive": "fable",
                "friendly": "nova",
            }
            voice = voice_map.get(params.style, "onyx")
            
            response = await self._client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=1.0 + (params.reverb * 0.2), 
            )
            return await response.read()
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            return b""

    async def transcribe(self, audio_data: bytes) -> str:
        try:
            # Whisper requires a file-like object with a name attribute.
            from io import BytesIO
            audio_file = BytesIO(audio_data)
            audio_file.name = "audio.wav"
            
            response = await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
            return response.text
        except Exception as e:
            logger.error(f"OpenAI STT error: {e}")
            return ""
