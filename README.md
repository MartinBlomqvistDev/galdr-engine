# GALDR Engine

Voice-first AI orchestration for interactive storytelling. Headless, event-driven, designed for low-latency narrative delivery.

A dramatist authors a directed graph of narrative nodes. Within each node, an AI character improvises dialogue freely. The two layers never cross: graph structure is the dramatist's domain, language is the AI's. The two layers are graph control (story structure, authored) and character direction (language, generated).

---

## What it does

- **GPS-triggered narrative (planned)**: nodes can carry a GPS anchor, but proximity does not yet activate nodes or advance the story. Location-triggered play for outdoor and site-specific performance is the next step for this layer.
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
└── tests/                         # 189 tests across 12 modules
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

GPS-triggered scenarios, multi-character casts and outdoor performance are planned and not exercised in this PoC.

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

## Latency profile (n=44 generated turns, benchmarks 03-09, Azure gpt-4o + Azure AI Speech)

Three instruments measure three disjoint, sequential segments. `pre_latency` covers
pipeline steps 1-4, `first_token_ms` covers the narration LLM round trip, and `[STREAM TTFA]`
starts when `narrate_stream()` begins, which is *after* the pipeline has returned. The first
`[TTS]` line after `[STREAM TTFA]` is the synthesis of the turn's first sentence. Because
the segments do not overlap, the honest end-to-end figure is their sum. The clock starts
when the transcript is ready; the time from end of speech to transcript is not logged.

Every row is computed over the same 44 generated turns, pairing each turn's segments;
percentiles use linear interpolation, as in `parse_benchmark.py`. Benchmark 02 is left out:
it synthesised and played each sentence in one blocking call, so its TTS figures include
playback. The logs for benchmarks 02-09 are in `app/`. The player's own lines in them are
redacted; every timing line is unchanged.

| Segment | mean | p50 | p95 |
|---------|------|-----|-----|
| Pipeline steps 1-4 (intent-matching LLM call, then dice, state, transition) | 713ms | 669ms | 906ms |
| `[STREAM TTFA]` (LLM call -> first sentence) | 1936ms | 1848ms | 3255ms |
| Azure OpenAI first token (inside the above) | 1933ms | 1842ms | 3254ms |
| Azure TTS synthesis, first sentence of the turn | 342ms | 326ms | 611ms |
| **Input -> first audio (sum, paired n=44)** | **2991ms** | **2914ms** | **4401ms** |

Time to first audio is therefore about **2.9s at p50**, against an original 500ms design
target that a cloud LLM pipeline does not reach. Per-observation median shares: narration
LLM 63%, steps 1-4 24%, TTS 11%.

The LLM round trip is the bottleneck and is measured directly: `first_token_ms` p50 1842ms
over n=44 (min 815ms, max 4401ms). It accounts for essentially all of `[STREAM TTFA]`; the
sentence splitter adds under 10ms. Steps 1-4 contribute 669ms at p50, and that time is a
second cloud call: intent matching sends the player's words to gpt-4o, which picks one of
the node's authored actions. Dice, state mutation and the node transition take about 1ms.
Each generated turn is therefore two LLM calls in sequence. An earlier local-inference
estimate (roughly 950-1050ms) assumed the steps 1-4 time would remain; since that time is
itself an LLM call it would move local too, and a local figure has not been measured. TTS
cold start (5270ms on the first synthesis) is not structural; a `warmup()` at session start
opens the Azure synthesiser WebSocket and eliminates it.

Two earlier errors, kept because the corrections are the useful part:

- Earlier revisions reported input-to-first-audio as ~2040ms with the LLM at 62% (~1264ms).
  That 1264 was never measured: it is 1844 minus an assumed 580ms pipeline, on the
  assumption that `[STREAM TTFA]` starts at player input. It does not. `t0` is set inside
  `narrate_stream()`, by which point steps 1-4 have already run, so subtracting the pipeline
  removed time that belongs in the total.
- The next revision reported 2.7s at p50 over n=46. It added 196ms to every turn, the median
  of all warm syntheses in the logs, instead of the measured synthesis of each turn's first
  sentence, which is slower (p50 326ms), and it used a different percentile method. The table
  above uses the measured first synthesis of every turn.

Full design reasoning in [app/ARCHITECTURE.md](app/ARCHITECTURE.md).
