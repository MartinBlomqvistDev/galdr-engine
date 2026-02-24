# GALDR Engine

Voice-first orchestration for interactive fiction — headless, event-driven, and designed for low-latency narrative delivery.

### Core Principle: Separation of Concerns
GALDR implements a strict boundary between dramaturgical structure and generative language:
- **Nod-regi (Graph Control):** The dramatist defines the scene structure, mechanics, and branching via a directed graph.
- **Prompt-regi (Creative Direction):** The AI improvises dialogue within the specific constraints of the current node.

This architecture ensures narrative consistency (the AI cannot break the story graph) while maintaining conversational fluidity.

---

## Processing Pipeline

1. **Intent Matching**: Maps player input to node actions (LLM-based with heuristic fallback).
2. **Mechanical Resolution**: RPG-style skill checks (D&D 5e-inspired) validated via Pydantic.
3. **State Mutation**: Atomic updates to GameState (inventory, flags, HP).
4. **Context Construction**: Dynamic system prompt generation from node metadata and world state.
5. **Inference**: LLM generation and deterministic content filtering.
6. **Synthesis**: TTS generation with per-node voice parameters (pitch, reverb, style).

See [ARCHITECTURE.md](ARCHITECTURE.md) for a technical deep-dive into the 8-step orchestration loop and p95 latency targets.

---

## Repo layout

```
galdr/
├── core/
│   ├── engine.py        # The 8-step orchestration loop
│   ├── nodes.py         # NarrativeNode, Condition, Consequence, Scenario
│   ├── prompt_regi.py   # Builds LLM system prompts from node + game state
│   ├── state.py         # GameState, Character, World — all Pydantic
│   └── dice.py          # Skill checks, DC, nat 20/1, narrative quality tiers
├── voice/
│   ├── tts.py           # TTS with per-node voice morphing (pitch, tempo, emotion)
│   └── stt.py           # Whisper transcription
├── api/
│   ├── routes.py        # REST (session management, input, state inspection)
│   └── websocket.py     # Real-time handler — text in, text+audio out
├── geo/
│   └── geofence.py      # Haversine proximity + reverb from distance
├── guardrails/
│   └── filter.py        # Hard global blocks + soft per-scene topic filtering
└── db/
    └── repository.py    # In-memory for now, Postgres-shaped for later

scenarios/
└── ekokammaren.json     # 8-node GPS story set in Malmö city centre

tests/                   # 46 tests including two full end-to-end playthroughs
play.py                  # Terminal client — playable offline, no API key needed
static/index.html        # Minimal browser client
```

---

## Running it

```bash
pip install -e .

# Offline — full game mechanics, scripted responses, no key needed
python play.py

# With API server
uvicorn galdr.main:app --reload
# Web UI:   http://localhost:8000
# API docs: http://localhost:8000/docs

# With real AI dialogue (BYOK)
cp .env.example .env    # add OPENAI_API_KEY
uvicorn galdr.main:app --reload

# Tests
python -m pytest tests/ -v
```

---

## API

```
POST /api/v1/sessions                  New session
POST /api/v1/sessions/{id}/enter       Trigger node opening text
POST /api/v1/sessions/{id}/input       Player input → engine response
GET  /api/v1/sessions/{id}/state       Current state snapshot
GET  /api/v1/scenario                  Loaded scenario info

WS   /ws/{session_id}                  Real-time: text in, text+audio out
```

---

## BYOK

Set `OPENAI_API_KEY` in `.env`. The engine runs without it — offline mode uses the scenario's scripted texts and full game mechanics. Swapping the LLM or TTS backend is a one-file change.

---

## Demo: Ekokammaren

The included scenario is *Malmö's Hidden Voices* — a GPS-triggered story set in Malmö city centre where players follow a disembodied voice (The Echo) through historical locations. Built to test the engine outdoors, with reverb adjusting dynamically as players approach each node.

Runs fine locally without GPS. Use number keys or free text to navigate.

---

## Key design choices

| Choice | Why |
|--------|-----|
| Pydantic for all state | Mutations fail loudly, not silently |
| Skill checks before LLM generation | Mechanics drive the story — AI narrates the outcome |
| Nod-regi as a directed graph | AI can improvise within scenes, can't skip between them |
| Dual-layer content filtering | Global hard blocks + per-scene soft blocks for narrative context |
| Offline-first fallback | The engine should be demonstrable without credentials |

Full design reasoning in [ARCHITECTURE.md](ARCHITECTURE.md).
