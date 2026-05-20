"""VAD (Voice Activity Detection) utility for barge-in interrupt.

Uses sounddevice energy threshold to detect speech onset. Much lower latency
than Azure continuous recognition: ~20ms (one audio block) vs ~300-500ms
(Azure recognition latency after full utterance).

Usage pattern:
    def stop_tts():
        sd.stop()           # or synthesizer.stop_speaking_async()

    pcm_bytes = record_until_silence(on_speech_start=stop_tts)
    if pcm_bytes:
        text = stt._transcribe_pcm_sync(pcm_bytes)
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
_BLOCK_MS = 20
_BLOCK_SIZE = int(SAMPLE_RATE * _BLOCK_MS / 1000)  # 320 samples @ 16kHz
_PRE_ROLL_BLOCKS = 10   # 200ms captured before threshold fires
_SILENCE_BLOCKS = 40    # 800ms of silence = utterance complete
_MAX_BLOCKS = 500        # 10s hard cap


def record_until_silence(
    on_speech_start: Callable[[], None] | None = None,
    energy_threshold: float = 0.015,
    sample_rate: int = SAMPLE_RATE,
    silence_ms: int = 800,
    max_ms: int = 10000,
    stop_event: threading.Event | None = None,
) -> bytes:
    """Monitor mic for speech; record and return the utterance as PCM int16 bytes.

    Blocks until either:
    - speech detected → silence reached (utterance complete), OR
    - max_ms elapsed (safety cap), OR
    - stop_event is set (caller signals audio playback finished)

    Returns b"" if no speech was detected.

    on_speech_start: called from the audio thread the moment energy exceeds
    threshold. Use it to stop TTS playback immediately.

    energy_threshold: RMS threshold (float32, range 0-1). 0.015 works well for
    quiet rooms; raise to 0.04-0.05 if TTS bleeds into mic through speakers.

    stop_event: when set by the caller (e.g. audio finished playing), VAD exits
    immediately. Prevents blocking for max_ms when no barge-in occurred.
    """
    block_size = int(sample_rate * _BLOCK_MS / 1000)
    silence_blocks = int(silence_ms / _BLOCK_MS)
    max_blocks = int(max_ms / _BLOCK_MS)

    pre_roll: deque[np.ndarray] = deque(maxlen=_PRE_ROLL_BLOCKS)
    recording_chunks: list[np.ndarray] = []

    speech_started = threading.Event()
    done_event = threading.Event()

    recording = False
    silence_count = 0
    block_count = 0
    start_called = False

    def _callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        nonlocal recording, silence_count, block_count, start_called

        # Caller signalled that audio finished — stop monitoring
        if stop_event and stop_event.is_set() and not recording:
            done_event.set()
            raise sd.CallbackStop()

        chunk = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(chunk ** 2)))

        if not recording:
            pre_roll.append(chunk)
            if rms > energy_threshold:
                recording = True
                speech_started.set()
                if on_speech_start and not start_called:
                    start_called = True
                    on_speech_start()
                recording_chunks.extend(pre_roll)
                recording_chunks.append(chunk)
        else:
            recording_chunks.append(chunk)
            block_count += 1
            if rms < energy_threshold * 0.5:
                silence_count += 1
            else:
                silence_count = 0
            if silence_count >= silence_blocks or block_count >= max_blocks:
                done_event.set()
                raise sd.CallbackStop()

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_size,
            callback=_callback,
        ):
            done_event.wait(timeout=max_ms / 1000 + 1.0)
    except Exception:
        pass

    if not speech_started.is_set() or not recording_chunks:
        return b""

    audio = np.concatenate(recording_chunks)
    pcm_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    return pcm_int16.tobytes()
