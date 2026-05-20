"""Audio post-processing utilities for GALDR voice loop."""

from __future__ import annotations

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

_WAV_HEADER_BYTES = 44  # Standard RIFF WAV header size for Riff16Khz16BitMonoPcm


def apply_reverb(
    pcm_int16: np.ndarray,
    reverb: float,
    sample_rate: int = 16000,
) -> np.ndarray:
    """Apply room reverb to PCM int16 audio via exponential decay convolution.

    reverb: 0.0 (dry) to 1.0 (heavy echo). Values <= 0.0 are a no-op.
    Returns a PCM int16 array of the same length as input.

    Uses a synthetic RIR (exponential decay) so no external impulse response
    files are required. Biome-specific RIR files can replace this later
    (load from a path, convolve the same way) without touching call sites.
    """
    if reverb <= 0.0:
        return pcm_int16

    from scipy.signal import fftconvolve

    t0 = time.perf_counter()

    # RIR length scales with reverb level: 50ms (subtle) to 750ms (heavy)
    rir_ms = 50 + int(reverb * 700)
    rir_len = int(sample_rate * rir_ms / 1000)
    decay = 6.9 / (rir_ms / 1000)  # reaches -60dB at rir_ms
    t = np.arange(rir_len, dtype=np.float32) / sample_rate
    rir = np.exp(-decay * t)
    rir[0] = 1.0  # preserve the direct (dry) sound

    audio_f = pcm_int16.astype(np.float32) / 32767.0
    wet = fftconvolve(audio_f, rir)[: len(audio_f)]

    # Wet/dry mix: reverb=1.0 gives 45% wet, reverb=0.1 gives ~4.5% wet
    wet_gain = reverb * 0.45
    dry_gain = 1.0 - wet_gain * 0.3
    mixed = dry_gain * audio_f + wet_gain * wet

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "[REVERB] reverb=%.2f rir_ms=%d samples=%d proc_ms=%.1f",
        reverb, rir_ms, len(pcm_int16), elapsed_ms,
    )

    return (np.clip(mixed, -1.0, 1.0) * 32767).astype(np.int16)


def wav_bytes_to_pcm_int16(wav_bytes: bytes) -> np.ndarray:
    """Strip the 44-byte RIFF WAV header and return a raw int16 PCM array.

    Only valid for Riff16Khz16BitMonoPcm output — the format Azure TTS uses
    when synthesize() is called. Do not use on arbitrary WAV files.
    """
    return np.frombuffer(wav_bytes[_WAV_HEADER_BYTES:], dtype=np.int16)
