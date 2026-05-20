"""Azure-backed implementations of LLMService, TTSService, and STTService.

LLM:   Azure OpenAI (AsyncAzureOpenAI)
TTS:   Azure AI Speech (neural voice, SSML with narration-professional style)
STT:   Azure AI Speech (recognize_once for normal input; PCM transcription for VAD barge-in)

Barge-in flow: sounddevice VAD detects speech onset (~20ms), stops TTS immediately,
captures utterance via galdr.utils.vad.record_until_silence, then transcribes
the captured PCM via _transcribe_pcm_sync. Much lower interrupt latency than
Azure continuous recognition (~300-500ms after utterance).

All three log per-call latency and token counts.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

from openai import AsyncAzureOpenAI
from galdr.config import settings
from galdr.services.interfaces import LLMService, TTSService, STTService, VoiceParams

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AzureOpenAIService:
    """LLM narration via Azure OpenAI. Implements LLMService."""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2025-01-01-preview",
    ) -> None:
        self._client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
        )
        self.deployment = deployment

    async def generate_text(self, messages: list[Any], **kwargs) -> str:
        max_tokens = kwargs.get("max_tokens", 250)
        temperature = kwargs.get("temperature", 0.8)
        t0 = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            usage = response.usage
            logger.info(
                "[LLM CALL] tokens_in=%d tokens_out=%d latency_ms=%.0f",
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
                latency_ms,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Azure OpenAI error: %s", e)
            raise

    async def generate_text_stream(self, messages: list[Any], **kwargs):
        """Stream LLM tokens as they arrive. Yields str chunks.

        First token typically arrives in 300-800ms. Callers should pipe through
        galdr.utils.sentence_splitter.split_sentences for TTS-ready output.
        """
        max_tokens = kwargs.get("max_tokens", 250)
        temperature = kwargs.get("temperature", 0.8)
        t0 = time.perf_counter()
        first_token = True
        try:
            stream = await self._client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for event in stream:
                content = event.choices[0].delta.content if event.choices else None
                if content:
                    if first_token:
                        logger.info("[LLM STREAM] first_token_ms=%.0f", (time.perf_counter() - t0) * 1000)
                        first_token = False
                    yield content
            logger.info("[LLM STREAM] total_ms=%.0f", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            logger.error("Azure OpenAI stream error: %s", e)
            raise


class AzureSpeechTTSService:
    """TTS via Azure AI Speech (neural voice, SSML).

    synthesize()           returns WAV bytes (Protocol contract).
    speak()                plays to speaker, blocks until done.
    speak_with_barge_in()  plays to speaker while STT listens; cancels on speech.
    """

    # Narrator voice candidates (swap _NARRATOR for A/B testing):
    # US English (male)
    #   en-US-RyanMultilingualNeural  — warm, clear, multilingual
    #   en-US-DavisNeural             — expressive, darker register
    #   en-US-ChristopherNeural       — steady, reliable narration
    # US English (female)
    #   en-US-JaneNeural              — calm authority  <- current
    #   en-US-SaraNeural              — clear, measured
    # British English (female)
    #   en-GB-SoniaNeural             — warm but measured, strong narrator quality
    # Other English (female)
    #   en-IE-EmilyNeural             — Irish, quiet authority
    #   en-AU-NatashaNeural           — Australian, dry and grounded
    #   en-NZ-MollyNeural             — New Zealand, understated
    _NARRATOR = "en-GB-SoniaNeural"

    _VOICE_MAP = {
        "narrator":    _NARRATOR,
        "mystic":      _NARRATOR,
        "nostalgic":   _NARRATOR,
        "warm":        _NARRATOR,
        "neutral":     _NARRATOR,
        "whisper":     _NARRATOR,
        "threatening": _NARRATOR,
        "aggressive":  _NARRATOR,
        "friendly":    "en-US-JennyNeural",
    }
    _DEFAULT_VOICE = _NARRATOR

    def __init__(self, key: str, region: str) -> None:
        self._key = key
        self._region = region
        # Cached synthesizers — avoids WebSocket reconnect overhead (~3-5s) on each call.
        self._speaker_synth = None
        self._bytes_synth = None

    def _make_base_config(self):
        import azure.cognitiveservices.speech as speechsdk
        cfg = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
        return cfg

    def _get_speaker_synth(self):
        import azure.cognitiveservices.speech as speechsdk
        if self._speaker_synth is None:
            cfg = self._make_base_config()
            audio_cfg = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
            self._speaker_synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_cfg)
        return self._speaker_synth

    def _get_bytes_synth(self):
        import azure.cognitiveservices.speech as speechsdk
        if self._bytes_synth is None:
            cfg = self._make_base_config()
            # Raw PCM — no WAV header, directly usable as np.int16 array
            cfg.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
            )
            self._bytes_synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
        return self._bytes_synth

    def warmup(self) -> None:
        """Initialize both synthesizer WebSocket connections before the first real call.

        Azure Speech SDK lazy-connects on first synthesize — typically 3-5s.
        Calling this at startup hides that cost before player interaction begins.
        """
        t0 = time.perf_counter()
        self._get_speaker_synth()
        self._get_bytes_synth()
        logger.info("[TTS WARMUP] synthesizers ready in %.0fms", (time.perf_counter() - t0) * 1000)

    @staticmethod
    def _build_ssml(text: str, voice: str, rate: str = "0.9") -> str:
        escaped = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        return (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xml:lang="en-US">'
            f'<voice name="{voice}">'
            f'<prosody rate="{rate}">{escaped}</prosody>'
            '</voice>'
            '</speak>'
        )

    async def synthesize(self, text: str, params: VoiceParams) -> bytes:
        voice = self._VOICE_MAP.get(params.style, self._DEFAULT_VOICE)
        ssml = self._build_ssml(text, voice)
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        audio = await loop.run_in_executor(None, self._synth_to_bytes, ssml)
        logger.info("[TTS] voice=%s chars=%d latency_ms=%.0f", voice, len(text), (time.perf_counter() - t0) * 1000)
        return audio

    def _synth_to_bytes(self, ssml: str) -> bytes:
        import azure.cognitiveservices.speech as speechsdk
        result = self._get_bytes_synth().speak_ssml_async(ssml).get()
        if result is None:
            logger.error("TTS (bytes) failed: no result")
            return b""
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        logger.error("TTS (bytes) failed: %s", result.reason)
        return b""

    async def speak(self, text: str, params: VoiceParams) -> None:
        voice = self._VOICE_MAP.get(params.style, self._DEFAULT_VOICE)
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        if settings.reverb_processing_enabled and params.reverb > 0.0:
            import numpy as np
            import sounddevice as sd
            from galdr.utils.audio import apply_reverb, wav_bytes_to_pcm_int16
            wav = await self.synthesize(text, params)
            audio_array = apply_reverb(wav_bytes_to_pcm_int16(wav), params.reverb, 16000)
            await loop.run_in_executor(None, lambda: (sd.play(audio_array, samplerate=16000), sd.wait()))
        else:
            ssml = self._build_ssml(text, voice)
            await loop.run_in_executor(None, self._synth_to_speaker, ssml)
        logger.info("[TTS->speaker] voice=%s chars=%d latency_ms=%.0f", voice, len(text), (time.perf_counter() - t0) * 1000)

    def _synth_to_speaker(self, ssml: str) -> None:
        import azure.cognitiveservices.speech as speechsdk
        result = self._get_speaker_synth().speak_ssml_async(ssml).get()
        if result is None:
            logger.error("TTS (speaker) failed: no result")
            return
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.error("TTS (speaker) failed: %s", result.reason)

    async def speak_with_barge_in(
        self,
        text: str,
        params: VoiceParams,
        stt: "AzureSpeechSTTService",
    ) -> str:
        voice = self._VOICE_MAP.get(params.style, self._DEFAULT_VOICE)
        ssml = self._build_ssml(text, voice)
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._speak_barge_in_sync, ssml, stt, params.reverb)
        latency_ms = (time.perf_counter() - t0) * 1000
        if result:
            logger.info("[TTS->barge-in] chars=%d latency_ms=%.0f text=%r", len(text), latency_ms, result[:40])
        else:
            logger.info("[TTS->speaker] voice=%s chars=%d latency_ms=%.0f", voice, len(text), latency_ms)
        return result

    def _speak_barge_in_sync(self, ssml: str, stt: "AzureSpeechSTTService", reverb: float = 0.0) -> str:
        """Play TTS while monitoring mic via sounddevice VAD.

        Stops TTS within ~20ms of speech onset (energy threshold) rather than
        waiting for Azure recognition to complete (~300-500ms).

        When reverb is enabled, synthesizes to PCM first so sounddevice can be
        interrupted via sd.stop() — same mechanism as ElevenLabs barge-in.
        """
        import azure.cognitiveservices.speech as speechsdk
        from galdr.utils.vad import record_until_silence

        speak_done = threading.Event()

        if settings.reverb_processing_enabled and reverb > 0.0:
            import sounddevice as sd
            from galdr.utils.audio import apply_reverb, wav_bytes_to_pcm_int16
            wav = self._synth_to_bytes(ssml)
            audio_array = apply_reverb(wav_bytes_to_pcm_int16(wav), reverb, 16000)

            def do_speak():
                sd.play(audio_array, samplerate=16000)
                sd.wait()
                speak_done.set()

            threading.Thread(target=do_speak, daemon=True).start()
            pcm = record_until_silence(on_speech_start=sd.stop)
        else:
            synthesizer = self._get_speaker_synth()

            def do_speak():
                synthesizer.speak_ssml_async(ssml).get()
                speak_done.set()

            threading.Thread(target=do_speak, daemon=True).start()
            def _stop_synth() -> None:
                synthesizer.stop_speaking_async()
            pcm = record_until_silence(on_speech_start=_stop_synth)

        if not pcm:
            speak_done.wait(timeout=2.0)
            return ""

        t0 = time.perf_counter()
        text = stt._transcribe_pcm_sync(pcm)
        logger.info("[BARGE-IN] interrupt->transcribe=%.0fms text=%r", (time.perf_counter() - t0) * 1000, text[:40])
        return text



class AzureSpeechSTTService:
    """STT via Azure AI Speech.

    transcribe()      transcribes WAV bytes (Protocol contract).
    listen_from_mic() VAD-based mic capture (voice loop).
    """

    def __init__(self, key: str, region: str, language: str = "en-US") -> None:
        self._key = key
        self._region = region
        self._language = language

    def _make_speech_config(self):
        import azure.cognitiveservices.speech as speechsdk
        cfg = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
        cfg.speech_recognition_language = self._language
        return cfg

    async def transcribe(self, audio_data: bytes) -> str:
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, self._from_bytes_sync, audio_data)
        logger.info("[STT] bytes=%d chars=%d latency_ms=%.0f", len(audio_data), len(text), (time.perf_counter() - t0) * 1000)
        return text

    async def listen_from_mic(self) -> str:
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, self._from_mic_sync)
        logger.info("[STT<-mic] chars=%d latency_ms=%.0f", len(text), (time.perf_counter() - t0) * 1000)
        return text

    def _from_bytes_sync(self, audio_data: bytes) -> str:
        import azure.cognitiveservices.speech as speechsdk
        stream = speechsdk.audio.PushAudioInputStream()
        stream.write(audio_data)
        stream.close()
        audio_config = speechsdk.audio.AudioConfig(stream=stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._make_speech_config(), audio_config=audio_config
        )
        return self._get_result(recognizer)

    def _from_mic_sync(self) -> str:
        import azure.cognitiveservices.speech as speechsdk
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._make_speech_config(), audio_config=audio_config
        )
        return self._get_result(recognizer)

    def _transcribe_pcm_sync(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM int16 bytes via Azure STT. Used after VAD barge-in capture."""
        import azure.cognitiveservices.speech as speechsdk
        t0 = time.perf_counter()
        fmt = speechsdk.audio.AudioStreamFormat(
            samples_per_second=sample_rate,
            bits_per_sample=16,
            channels=1,
        )
        stream = speechsdk.audio.PushAudioInputStream(stream_format=fmt)
        stream.write(pcm_bytes)
        stream.close()
        audio_cfg = speechsdk.audio.AudioConfig(stream=stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=self._make_speech_config(), audio_config=audio_cfg
        )
        text = self._get_result(recognizer)
        logger.info("[STT<-vad] bytes=%d chars=%d latency_ms=%.0f", len(pcm_bytes), len(text), (time.perf_counter() - t0) * 1000)
        return text

    @staticmethod
    def _get_result(recognizer) -> str:
        import azure.cognitiveservices.speech as speechsdk
        result = recognizer.recognize_once()
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        if result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning("STT: no speech detected")
        else:
            logger.error("STT failed: %s", result.reason)
        return ""
