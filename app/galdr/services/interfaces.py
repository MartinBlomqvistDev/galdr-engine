from typing import Protocol, runtime_checkable, Optional
from pydantic import BaseModel

class VoiceParams(BaseModel):
    character_name: str
    emotion: str = "neutral"
    style: str = "narrator"
    reverb: float = 0.0

@runtime_checkable
class LLMService(Protocol):
    async def generate_text(self, messages: list[dict[str, str]], **kwargs) -> str:
        ...

@runtime_checkable
class TTSService(Protocol):
    async def synthesize(self, text: str, params: VoiceParams) -> bytes:
        ...

@runtime_checkable
class STTService(Protocol):
    async def transcribe(self, audio_data: bytes) -> str:
        ...
