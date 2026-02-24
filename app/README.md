# GALDR Engine

An agentic AI engine for voice-first interactive storytelling — no screen, no GUI, just conversation and sound.

The core idea: a dramatist designs a story as a graph of narrative nodes. An AI character lives inside those nodes and improvises dialogue freely. The two never overlap — structure is the dramatist's job, language is the AI's. We call this split *nod-regi* (graph control) and *prompt-regi* (character direction).

---

## What problem this solves

Current voice AI either gives you a chatbot (unconstrained, wanders off-story) or an audio book (scripted, static). GALDR sits between: the story has bones the AI can't break, but within each scene the AI is genuinely responsive. Player says something unexpected — the character rolls with it, within the scene's intent.

Every player action also goes through a proper RPG skill check (D&D 5e-flavoured) before the AI generates a response. The dice result shapes what the AI says — not the other way around.

---

## Architecture sketch

```
Player input (text or voice)
         │
         ▼
    Intent matching
    (LLM constrained to available node actions, with offline keyword fallback)
         │
         ▼
    Skill check  ←── if the action requires one (Pydantic-validated)
         │
         ▼
    State mutation  ←── consequences applied atomically
         │
         ▼
    Prompt builder  ←── nod-regi + state + dice result → system prompt
         │
         ▼
       LLM
         │
         ▼
    Content filter  ←── global + per-node forbidden topics
         │
         ▼
    TTS  ←── voice morphing params from node definition
         │
         ▼
    Response (text + audio + updated state)
```

This order matters — see [ARCHITECTURE.md](ARCHITECTURE.md) for why each step sits where it does.

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
