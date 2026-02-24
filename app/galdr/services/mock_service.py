from galdr.services.interfaces import LLMService, TTSService, VoiceParams

class MockAIService(LLMService, TTSService):
    def __init__(self):
        self.last_messages = []
        self.next_response = "Mock AI response"

    async def generate_text(self, messages: list[dict[str, str]], **kwargs) -> str:
        self.last_messages = messages
        return self.next_response

    async def synthesize(self, text: str, params: VoiceParams) -> bytes:
        return b"fake_audio_data"
