# GALDR Engine

Voice-first AI orchestration for interactive storytelling. Headless, event-driven, designed for low-latency narrative delivery.

A dramatist authors a directed graph of narrative nodes. Within each node, an AI character improvises dialogue freely. The two layers never cross: graph structure is the dramatist's domain, language is the AI's. The two layers are graph control (story structure, authored) and character direction (language, generated).

---

## What it does

- **GPS-triggered narrative**: nodes activate on proximity. Reverb adjusts dynamically as the player approaches. Built for outdoor and site-specific performance.
- **D&D 5e skill checks**: every player action is mechanically resolved before the LLM generates. Dice result shapes what the AI says; the AI never decides outcomes.
- **Streaming TTS pipeline**: LLM token stream splits into sentences. Sentence N+1 synthesizes while N plays. Near-zero inter-sentence gap after the first sentence.
- **Two-layer narrator tonality**: authored `VoiceParams` per node (TTS acoustic delivery, static dramatist intent) + game state injected into system prompt (LLM narrative register, dynamic).
- **Ambient context layer**: daylight phase, weather (WMO codes), biome tags injected per node. The narrator knows the time of day and conditions without being told in-scene.
- **Offline-first**: full game mechanics (dice, flags, transitions) run without any API key. Mock services substitute AI in tests and demos.
- **Multi-backend**: Azure OpenAI + Azure Speech (current), ElevenLabs TTS (high fidelity, optional), OpenAI (alternative LLM), mock (offline/CI).

---

## Processing pipeline

```text
Player speech (microphone)
         |
         v
    Azure Speech STT
         |
         v
    GPS + ambient context    <-- proximity check, daylight, weather
         |
         v
    Intent matching          <-- LLM constrained to node's available actions
         |
         v
    Skill check              <-- gates state mutations before LLM is called
         |
         v
    State mutation           <-- consequences applied atomically (Pydantic-validated)
         |
         v
    Prompt director          <-- 8-layer system prompt: node + game state + dice result
         |
         v
    LLM (streaming token stream)
         |
         v
    Sentence splitter        <-- splits live token stream into playable sentences
         |
         v
    TTS synthesis            <-- pipelined: sentence N+1 synthesizes while N plays
         |
         v
    Playback (sounddevice, 16kHz, reverb post-processing)
```

The sentence pipeline hides synthesis latency behind playback. Near-zero inter-sentence gap after the first sentence arrives from the token stream.

---

## Repo layout

```text
app/
├── galdr/
│   ├── core/
│   │   ├── engine.py              # 8-step orchestration loop
│   │   ├── nodes.py               # NarrativeNode, Condition, Consequence, Scenario
│   │   ├── prompt_director.py     # 8-layer system prompt builder
│   │   ├── state.py               # GameState, Character, World: all Pydantic
│   │   ├── dice.py                # Skill checks, DC, nat 20/1, narrative quality tiers
│   │   ├── saves.py               # Checkpoint persistence
│   │   └── calibration.py         # Stat calibration (legacy; replaced by diegetic emergence v3.2.0)
│   ├── services/
│   │   ├── interfaces.py          # VoiceParams, service protocols
│   │   ├── azure_service.py       # Azure OpenAI LLM + Azure Speech STT/TTS
│   │   ├── elevenlabs_service.py  # ElevenLabs TTS (higher fidelity, optional)
│   │   ├── openai_service.py      # OpenAI LLM backend (alternative)
│   │   └── mock_service.py        # Offline stubs: full mechanics, no API keys
│   ├── voice/
│   │   ├── tts.py                 # TTS abstraction layer
│   │   └── stt.py                 # STT abstraction layer
│   ├── api/
│   │   ├── routes.py              # REST: session management, input, state inspection
│   │   ├── websocket.py           # Real-time: text in, text+audio out
│   │   └── middleware.py          # Telemetry middleware (p95 latency tracking)
│   ├── geo/
│   │   └── geofence.py            # Haversine proximity + reverb from distance
│   ├── guardrails/
│   │   └── filter.py              # Hard global blocks + soft per-scene topic filtering
│   ├── ambient/
│   │   ├── context.py             # Ambient context builder (daylight + weather)
│   │   ├── daylight.py            # Daylight phase from lat/lon + time
│   │   └── weather.py             # WMO weather codes to narrator-facing descriptions
│   ├── db/
│   │   └── repository.py          # In-memory store (PostgreSQL-shaped for production)
│   ├── utils/
│   │   ├── sentence_splitter.py   # Async token stream -> sentence iterator
│   │   ├── audio.py               # Reverb post-processing (scipy fftconvolve)
│   │   └── vad.py                 # Voice activity detection for barge-in
│   ├── config.py                  # Pydantic Settings, all credentials from .env
│   └── main.py                    # FastAPI app entry point
├── scenarios/
│   └── calloused_prologue.json    # 19-node prologue (CALLOUSED exam PoC)
├── voice_play.py                  # Voice-only loop (CALLOUSED PoC entry point)
├── parse_benchmark.py             # Latency + word count analysis from log files
└── tests/                         # 182 tests across 12 modules
```

---

## Running

Requires Python 3.12 and a microphone.

```bash
pip install -e .

# CALLOUSED voice PoC
python app/voice_play.py
python app/voice_play.py --scenario app/scenarios/calloused_prologue.json

# FastAPI server
uvicorn galdr.main:app --reload

# Benchmark analysis
python app/parse_benchmark.py app/benchmark_01.log

# Tests
python -m pytest app/tests/ -v
```

---

## Configuration

Copy `.env.example` to `.env`:

```env
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=swedencentral

# Optional: falls back to Azure Speech TTS if absent
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...

# Optional
REVERB_PROCESSING_ENABLED=true
```

Without keys the engine runs in mock mode: full game mechanics, scripted node text, no live AI or TTS.

---

## Demo: CALLOUSED (Prologue)

The included scenario is CALLOUSED, a voice-only RPG and exam PoC. Player and Lo investigate a stopped geothermal vent on a glass crater floor. The ground cracks. The player falls through into an Ancestor Facility 50,000 years dormant: a ceramic maintenance unit on a fixed circuit, hundreds of sleeping Ancestors, a census frozen at 479 of 480. 19 nodes. D&D 5e mechanics. Diegetic stat emergence. No screen.

GPS-triggered scenarios, multi-character casts, and outdoor performance are engine capabilities not exercised in this PoC.

---

## Key design decisions

| Decision | Reason |
|----------|--------|
| Pydantic for all state | Mutations fail loudly, not silently |
| Skill checks before LLM generation | Mechanics drive the story; AI narrates the outcome, never decides it |
| 8-layer system prompt | Broadest constraints first, scene-specific last. Order is a funnel, not a list |
| LANGUAGE constraint in Layer 1 | Azure gpt-4o on swedencentral defaults to Swedish under dense context; Layer 1 placement overrides before generation direction is set |
| Streaming sentence pipeline | Sentence N+1 synthesises while N plays. Inter-sentence gap 86-450ms (p95), under the 500ms conversational threshold |
| Lazy token generator | `process_input_stream()` returns a generator; scripted nodes discard it without iterating, zero wasted LLM calls on scripted transitions |
| Two-layer tonality | Layer 1: authored VoiceParams per node (TTS acoustic, static). Layer 2: pressure/lo_trust/flags in system prompt (LLM register, dynamic) |
| Narrative flags in system prompt | LLM reads structured state, not conversation history. Narrator only references events that actually happened |

---

## Latency profile (n=46 across benchmarks 02-09, Azure gpt-4o + Azure AI Speech)

Three instruments measure three disjoint, sequential segments. `pre_latency` covers the
deterministic pipeline, `first_token_ms` covers the LLM round trip, and `[STREAM TTFA]`
starts when `narrate_stream()` begins, which is *after* the pipeline has returned. Because
the segments do not overlap, the honest end-to-end figure is their sum.

| Segment | mean | p50 | p95 |
|---------|------|-----|-----|
| Pipeline steps 1-4 (deterministic, pre-LLM) | 712ms | 672ms | 907ms |
| `[STREAM TTFA]` (LLM call -> first sentence) | 1902ms | 1844ms | 3286ms |
| Azure OpenAI first token (inside the above) | 1900ms | 1834ms | 3071ms |
| Azure TTS warm synthesis, sentence 1 | ~250ms | ~196ms | ~450ms |
| **Input -> first audio (sum, paired n=46)** | **2811ms** | **2726ms** | **4173ms** |

Time to first audio is therefore about **2.7s at p50**, against an original 500ms design
target that a cloud LLM pipeline does not reach. Per-observation median shares: LLM 67%,
deterministic pipeline 26%, TTS 7%.

The LLM round trip is the bottleneck and is measured directly: `first_token_ms` p50 1834ms
over n=46 (min 815ms, max 4401ms). It accounts for essentially all of `[STREAM TTFA]`; the
sentence splitter adds under 10ms. The deterministic pipeline contributes 672ms and is
network-independent, so it becomes the binding constraint if inference moves local:
published Ollama benchmarks on Apple Silicon put local first-token at 50-150ms, which would
give an estimated input-to-first-audio of roughly 950-1050ms. TTS cold start (5270ms on the
first synthesis) is not structural; a `warmup()` at session start opens the Azure synthesiser
WebSocket and eliminates it.

A note on an earlier error, kept because the correction is the useful part. Previous
revisions reported input-to-first-audio as ~2040ms with the LLM at 62% (~1264ms). That 1264
was never measured: it is 1844 minus an assumed 580ms pipeline, on the assumption that
`[STREAM TTFA]` starts at player input. It does not. `t0` is set inside `narrate_stream()`,
by which point steps 1-4 have already run, so subtracting the pipeline removed 672ms that
belongs in the total. The figures above sum the three measured segments instead.

Full design reasoning in [app/ARCHITECTURE.md](app/ARCHITECTURE.md).
