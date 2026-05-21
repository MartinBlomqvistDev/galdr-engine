"""GALDR – Voice-Only Loop (Azure PoC)

Designed for visually impaired players. No screen required.

Run:
    python voice_play.py
    python voice_play.py --scenario scenarios/the_lighthouse_keeper.json

TTS priority:
    1. ElevenLabs (if ELEVENLABS_API_KEY is set) — best quality
    2. Azure AI Speech en-US — fallback
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Force UTF-8 on Windows so em dashes and other Unicode in authored content
# don't appear as ? in the console. Must run before logging.basicConfig.
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from galdr.config import settings
from galdr.core.calibration import run_calibration
from galdr.core.engine import GaldrEngine
from galdr.core.nodes import Scenario
from galdr.core.saves import checkpoint_exists, delete_checkpoint, load_checkpoint, save_checkpoint
from galdr.services.azure_service import (
    AzureOpenAIService,
    AzureSpeechSTTService,
    AzureSpeechTTSService,
)
from galdr.services.elevenlabs_service import ElevenLabsTTSService
from galdr.services.interfaces import VoiceParams

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_NARRATOR_VOICE = VoiceParams(character_name="Narrator", style="narrator")


def _node_voice(node) -> VoiceParams:
    v = node.voice
    return VoiceParams(
        character_name=v.character_name,
        pitch_shift=v.pitch_shift,
        tempo=v.tempo,
        emotion=v.emotion,
        reverb=v.reverb,
        style=v.style,
    )



class _NullTTS:
    """Engine-internal stub. Engine calls synthesize() for state; voice loop handles playback directly."""

    async def synthesize(self, text: str, params: VoiceParams) -> bytes:
        return b""


async def speak(tts, text: str, voice: VoiceParams) -> None:
    """Plain playback -- no barge-in. Use only for system prompts where interruption is meaningless."""
    text = _clean_text(text)
    if not text:
        return
    if hasattr(tts, "speak"):
        await tts.speak(text, voice)
    else:
        audio = await tts.synthesize(text, voice)
        if audio:
            import numpy as np
            import sounddevice as sd
            audio_array = np.frombuffer(audio, dtype=np.int16)
            sd.play(audio_array, samplerate=16000)
            sd.wait()



async def narrate_stream(tts, token_stream, voice: VoiceParams) -> str:
    """Sentence-level streaming narration with synthesis pipelining.

    Pipes LLM token stream through the sentence splitter. First sentence
    synthesizes immediately on arrival. Each subsequent sentence synthesizes
    concurrently with playback of the previous one — same pipeline as
    narrate_sentences, applied to a live token stream.

    Without pipelining: synthesis + playback sequential per sentence (~2-5s gap).
    With pipelining: synthesis of N+1 overlaps playback of N (~0ms gap after first).

    Returns '' always.
    """
    import time
    import numpy as np
    import sounddevice as sd
    from galdr.utils.sentence_splitter import split_sentences

    if not hasattr(tts, "synthesize"):
        # Fallback for TTS services without synthesize()
        t0 = time.perf_counter()
        first = True
        _spoken: list[str] = []
        async for sentence in split_sentences(token_stream):
            _spoken.append(sentence)
            if first:
                logger.info("[STREAM TTFA] %.0fms to first sentence", (time.perf_counter() - t0) * 1000)
                first = False
            await speak(tts, sentence, voice)
        if _spoken:
            logger.info("[NARRATOR] %s", " ".join(_spoken))
        return ""

    loop = asyncio.get_event_loop()
    from galdr.utils.audio import apply_reverb
    from galdr.config import settings as _s

    def _play(audio: bytes) -> None:
        arr = np.frombuffer(audio, dtype=np.int16)
        if _s.reverb_processing_enabled and voice.reverb > 0.0:
            arr = apply_reverb(arr, voice.reverb, 16000)
        sd.play(arr, samplerate=16000)
        sd.wait()

    t0 = time.perf_counter()
    first = True
    pending: bytes | None = None
    synth_task = None
    _spoken: list[str] = []

    async for sentence in split_sentences(token_stream):
        _spoken.append(sentence)
        if first:
            logger.info("[STREAM TTFA] %.0fms to first sentence", (time.perf_counter() - t0) * 1000)
            first = False
            # Start synthesizing first sentence immediately
            synth_task = asyncio.create_task(tts.synthesize(sentence, voice))
        else:
            # Wait for previous synthesis, start next, play previous
            pending = await synth_task
            synth_task = asyncio.create_task(tts.synthesize(sentence, voice))
            if pending:
                await loop.run_in_executor(None, _play, pending)

    # Drain: play the last synthesized sentence
    if synth_task is not None:
        pending = await synth_task
        if pending:
            await loop.run_in_executor(None, _play, pending)

    if _spoken:
        logger.info("[NARRATOR] %s", " ".join(_spoken))
    return ""


_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')
_MD_NOISE = re.compile(r'\*{1,3}|_{1,2}|`|^#{1,6}\s*', re.MULTILINE)


def _clean_text(text: str) -> str:
    return _MD_NOISE.sub('', text).strip()


def _split_text_sentences(text: str) -> list[str]:
    """Split a scripted string into sentences for per-sentence TTS."""
    parts = _SENT_SPLIT.split(_clean_text(text))
    return [p.strip() for p in parts if p.strip()]


async def narrate_sentences(tts, text: str, voice: VoiceParams) -> str:
    """Sentence-level narration for scripted text with synthesis pipelining.

    Synthesizes sentence N+1 while N is playing — hides the per-call TTS
    latency (2-7s on Azure) behind playback duration. First sentence still
    has the full cold latency; subsequent sentences play with near-zero gap.
    """
    sentences = _split_text_sentences(text)
    if not sentences:
        return ""
    logger.info("[NARRATOR] %s", " ".join(sentences))
    if len(sentences) == 1 or not hasattr(tts, "synthesize"):
        for s in sentences:
            await speak(tts, s, voice)
        return ""

    import numpy as np
    import sounddevice as sd
    loop = asyncio.get_event_loop()

    from galdr.utils.audio import apply_reverb
    from galdr.config import settings as _s

    def _play(audio: bytes) -> None:
        arr = np.frombuffer(audio, dtype=np.int16)
        if _s.reverb_processing_enabled and voice.reverb > 0.0:
            arr = apply_reverb(arr, voice.reverb, 16000)
        sd.play(arr, samplerate=16000)
        sd.wait()

    pending = await tts.synthesize(sentences[0], voice)
    for i in range(len(sentences)):
        next_task = None
        if i + 1 < len(sentences):
            next_task = asyncio.create_task(tts.synthesize(sentences[i + 1], voice))
        await loop.run_in_executor(None, _play, pending)
        if next_task is not None:
            pending = await next_task
    return ""


def _build_tts():
    if settings.elevenlabs_api_key:
        logger.info("Initializing ElevenLabs TTS (High Fidelity)")
        return ElevenLabsTTSService(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )
    logger.info("Initializing Azure Speech TTS (Standard)")
    return AzureSpeechTTSService(
        key=settings.azure_speech_key,
        region=settings.azure_speech_region,
    )


async def voice_loop(scenario_path: Path) -> None:
    # 1. Setup Services
    llm = AzureOpenAIService(
        api_key=settings.azure_openai_api_key,
        endpoint=settings.azure_openai_endpoint,
        deployment=settings.azure_openai_deployment,
    )
    stt = AzureSpeechSTTService(
        key=settings.azure_speech_key,
        region=settings.azure_speech_region,
        language="en-US",
    )
    tts = _build_tts()
    if hasattr(tts, "warmup"):
        logger.info("[TTS] Pre-warming synthesizer connections...")
        await asyncio.get_event_loop().run_in_executor(None, tts.warmup)

    # 2. Initialize Engine — NullTTS prevents double-billing on synthesize()
    scenario = Scenario.load_from_file(scenario_path)
    engine = GaldrEngine(scenario=scenario, llm=llm, tts=_NullTTS())

    print("\n" + "=" * 50)
    print("              CALLOUSED")
    print("=" * 50)

    # 3. Resume from checkpoint or start fresh
    resuming = False
    if checkpoint_exists(scenario.id):
        await speak(tts, "A previous session was found. Do you want to continue from your last checkpoint? Say yes or no.", _NARRATOR_VOICE)
        print("\n[Listening for resume choice...]")
        resume_answer = await stt.listen_from_mic()
        if resume_answer.lower().strip().startswith("y"):
            saved_state = load_checkpoint(scenario.id)
            if saved_state:
                engine.sessions[saved_state.session_id] = saved_state
                state = saved_state
                resuming = True
                logger.info("[RESUME] Continuing as %s at node %s", state.character.name, state.current_node_id)
                await speak(tts, f"Welcome back, {state.character.name}. Biometrics confirmed.", _NARRATOR_VOICE)
            else:
                state = engine.create_session()
        else:
            delete_checkpoint(scenario.id)
            state = engine.create_session()
    else:
        state = engine.create_session()

    if not resuming:
        # Diegetic calibration — fires mid-game at calibration_node, not at startup
        if scenario.calibration_enabled:
            state.character.stats = await run_calibration(
                llm=llm,
                speak=lambda text: speak(tts, text, _NARRATOR_VOICE),
                listen=stt.listen_from_mic,
            )
            logger.info("[CALIBRATION DONE] stats=%s", state.character.stats.model_dump())

    # calibration_done tracks whether diegetic mid-game calibration has fired this session
    calibration_done = resuming  # already done if resuming from checkpoint

    # 4. Opening Narration — sentence-level playback; barge-in per sentence
    pending_input = ""
    if not resuming:
        initial_response = await engine.enter_node(state.session_id)
        opening_node = scenario.get_node(state.current_node_id)
        opening_voice = _node_voice(opening_node) if opening_node else _NARRATOR_VOICE
        pending_input = await narrate_sentences(tts, initial_response.text, opening_voice)
        if pending_input:
            logger.info("[BARGE-IN during opening] captured: %s", pending_input)

    # 5. Main Loop
    while True:
        state = engine.get_session(state.session_id)
        current_node = scenario.get_node(state.current_node_id)
        if not current_node:
            break

        # End node — opening already spoken, just exit
        if state.current_node_id in scenario.end_nodes:
            break

        # Determine player input
        if pending_input:
            # Player already spoke during narration — use it directly
            user_input = pending_input
            pending_input = ""
            logger.info("[INPUT from barge-in]: %s", user_input)
        elif not current_node.actions and current_node.auto_next:
            # Auto-transition node — no player input required
            logger.info("[AUTO_NEXT] %s -> %s (delay=%.1fs)", current_node.id, current_node.auto_next, current_node.auto_delay_seconds)
            print(f"\n[AUTO] {current_node.id} -> {current_node.auto_next} in {current_node.auto_delay_seconds:.0f}s")
            # Diegetic calibration — fires on the designated node, once per session
            if scenario.calibration_node == current_node.id and not calibration_done:
                calibration_done = True
                state.character.stats = await run_calibration(
                    llm=llm,
                    speak=lambda text: speak(tts, text, _NARRATOR_VOICE),
                    listen=stt.listen_from_mic,
                )
                await speak(tts, "Registry entry sealed. Operational profile locked.", _NARRATOR_VOICE)
                logger.info("[CALIBRATION DONE] stats=%s", state.character.stats.model_dump())
            # Pre-advance: start enter_node during the delay window
            state.current_node_id = current_node.auto_next
            enter_task = asyncio.create_task(engine.enter_node(state.session_id))
            await asyncio.sleep(current_node.auto_delay_seconds)
            response = await enter_task
            next_node = scenario.get_node(state.current_node_id)
            if next_node:
                voice = _node_voice(next_node)
                pending_input = await narrate_sentences(tts, response.text, voice)
                if next_node.is_checkpoint:
                    save_checkpoint(state, scenario.id)
                    await speak(tts, "Biometrics stabilizing. Neural backup synchronized.", _NARRATOR_VOICE)
            continue
        elif current_node.actions:
            print(f"\n[Listening — node: {current_node.id}]")
            await speak(tts, "What do you do?", _node_voice(current_node))
            user_input = await stt.listen_from_mic()
        else:
            print("\n[Listening...]")
            user_input = await stt.listen_from_mic()

        if not user_input:
            logger.info("[LISTEN] no input detected — re-prompting")
            await speak(tts, "What do you do?", _node_voice(current_node))
            user_input = await stt.listen_from_mic()
            if not user_input:
                continue

        if user_input.lower().strip() in ["quit", "exit", "stop"]:
            break

        logger.info("[USER INPUT]: %s", user_input)

        # 6. Process Input — streaming: steps 1-4 execute now, LLM is lazy
        prev_node_id = state.current_node_id
        partial, token_stream = await engine.process_input_stream(state.session_id, user_input)

        state = engine.get_session(state.session_id)
        current_node = scenario.get_node(state.current_node_id)
        if not current_node:
            break

        voice = _node_voice(current_node)

        if state.current_node_id != prev_node_id and current_node.opening_text:
            # Node has scripted opening — discard token_stream (no LLM call made)
            state.record_dialog(
                current_node.voice.character_name,
                current_node.opening_text,
                node_id=current_node.id,
                emotion=current_node.voice.emotion,
            )
            pending_input = await narrate_sentences(tts, current_node.opening_text, voice)
            # End node reached — break before loop restarts and speaks again
            if state.current_node_id in scenario.end_nodes:
                break
            # Neural Sync — save on checkpoint nodes
            if current_node.is_checkpoint:
                save_checkpoint(state, scenario.id)
                await speak(tts, "Biometrics stabilizing. Neural backup synchronized.", _NARRATOR_VOICE)
        elif state.current_node_id == prev_node_id and current_node.opening_text:
            # Node didn't change and has scripted text — player gave unrecognized input.
            # Re-prompt rather than letting the LLM generate off-piste narration.
            await speak(tts, "What do you do?", _node_voice(current_node))
        else:
            # No scripted text — stream LLM response sentence by sentence
            pending_input = await narrate_stream(tts, token_stream, voice)

    logger.info("Session ended.")


def main() -> None:
    parser = argparse.ArgumentParser(description="GALDR — voice-only game loop")
    parser.add_argument(
        "--scenario",
        default="scenarios/the_lighthouse_keeper.json",
        help="Path to scenario JSON",
    )
    args = parser.parse_args()
    scenario_path = Path(__file__).parent / args.scenario

    try:
        asyncio.run(voice_loop(scenario_path))
    except KeyboardInterrupt:
        print("\n[interrupted]")


if __name__ == "__main__":
    main()
