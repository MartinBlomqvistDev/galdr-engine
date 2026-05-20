"""ElevenLabs TTS service for GALDR voice loop."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

from galdr.config import settings
from galdr.services.interfaces import VoiceParams

if TYPE_CHECKING:
    from galdr.services.azure_service import AzureSpeechSTTService

logger = logging.getLogger(__name__)

_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"


def _samplerate_from_format(fmt: str) -> int:
    """Parse samplerate from ElevenLabs output format string, e.g. 'pcm_16000' -> 16000."""
    for part in fmt.split("_"):
        if part.isdigit():
            return int(part)
    return 16000


class ElevenLabsTTSService:
    """TTS via ElevenLabs API using PCM output for low latency.

    synthesize()           returns PCM bytes (Protocol contract).
    speak()                plays to speaker, blocks until done.
    speak_with_barge_in()  plays while sounddevice VAD monitors; stops on speech onset, transcribes via Azure STT.
    """

    def __init__(self, api_key: str, voice_id: str = _DEFAULT_VOICE_ID) -> None:
        from elevenlabs.client import ElevenLabs
        self._client = ElevenLabs(api_key=api_key)
        self._voice_id_default = voice_id

    def _generate_pcm(self, text: str, voice_id: str) -> bytes:
        audio_gen = self._client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format=settings.elevenlabs_output_format,
        )
        return b"".join(chunk for chunk in audio_gen)

    async def synthesize(self, text: str, params: VoiceParams) -> bytes:
        voice_id = self._voice_id_default
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        pcm = await loop.run_in_executor(None, self._generate_pcm, text, voice_id)
        logger.info("[EL TTS] chars=%d bytes=%d latency_ms=%.0f", len(text), len(pcm), (time.perf_counter() - t0) * 1000)
        return pcm

    async def speak(self, text: str, params: VoiceParams) -> None:
        import numpy as np
        import sounddevice as sd
        voice_id = self._voice_id_default
        sr = _samplerate_from_format(settings.elevenlabs_output_format)
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        pcm = await loop.run_in_executor(None, self._generate_pcm, text, voice_id)
        audio_array = np.frombuffer(pcm, dtype=np.int16)
        if settings.reverb_processing_enabled and params.reverb > 0.0:
            from galdr.utils.audio import apply_reverb
            audio_array = apply_reverb(audio_array, params.reverb, sr)
        await loop.run_in_executor(None, lambda: (sd.play(audio_array, samplerate=sr), sd.wait()))
        logger.info("[EL TTS->speaker] chars=%d latency_ms=%.0f", len(text), (time.perf_counter() - t0) * 1000)

    async def speak_with_barge_in(
        self,
        text: str,
        params: VoiceParams,
        stt: "AzureSpeechSTTService",
    ) -> str:
        voice_id = self._voice_id_default
        t0 = time.perf_counter()
        loop = asyncio.get_event_loop()
        pcm = await loop.run_in_executor(None, self._generate_pcm, text, voice_id)
        result = await loop.run_in_executor(None, self._play_barge_in_sync, pcm, stt, params.reverb)
        latency_ms = (time.perf_counter() - t0) * 1000
        if result:
            logger.info("[EL TTS->barge-in] chars=%d latency_ms=%.0f text=%r", len(text), latency_ms, result[:40])
        else:
            logger.info("[EL TTS->speaker] chars=%d latency_ms=%.0f", len(text), latency_ms)
        return result

    def _play_barge_in_sync(self, pcm: bytes, stt: "AzureSpeechSTTService", reverb: float = 0.0) -> str:
        """Play PCM audio while monitoring mic via sounddevice VAD.

        Stops playback within ~20ms of speech onset (energy threshold) rather
        than waiting for Azure recognition to complete (~300-500ms).

        Guard period: VAD starts 350ms after playback begins. Prevents speaker
        bleed from immediately triggering barge-in when using speakers (not
        headphones). Raised threshold (0.04 vs 0.015) for the same reason.
        """
        import numpy as np
        import sounddevice as sd
        from galdr.utils.vad import record_until_silence

        sr = _samplerate_from_format(settings.elevenlabs_output_format)
        audio_array = np.frombuffer(pcm, dtype=np.int16)
        if settings.reverb_processing_enabled and reverb > 0.0:
            from galdr.utils.audio import apply_reverb
            audio_array = apply_reverb(audio_array, reverb, sr)

        speak_done = threading.Event()
        vad_stop = threading.Event()

        def do_speak():
            sd.play(audio_array, samplerate=sr)
            sd.wait()
            speak_done.set()
            vad_stop.set()  # signal VAD to exit immediately when audio finishes

        speak_thread = threading.Thread(target=do_speak, daemon=True)
        speak_thread.start()

        # Guard period: let audio start before VAD opens. Prevents the initial
        # speaker transient from triggering an immediate false barge-in.
        time.sleep(0.35)

        captured = record_until_silence(
            on_speech_start=sd.stop,
            energy_threshold=0.04,   # raised from 0.015 — speaker bleed protection
            stop_event=vad_stop,     # exits as soon as audio finishes, no 10s wait
        )

        if not captured:
            speak_done.wait(timeout=120.0)  # wait for audio to fully finish
            return ""

        t0 = time.perf_counter()
        text = stt._transcribe_pcm_sync(captured)
        logger.info("[BARGE-IN] interrupt->transcribe=%.0fms text=%r", (time.perf_counter() - t0) * 1000, text[:40])
        return text
