# GALDR — Architecture Notes

Design decisions, tradeoffs, and the reasoning behind them. Meant to be read alongside the code.

---

## The central problem

Generative AI in interactive fiction has two failure modes:

1. **Too free** — chatbot mode. The AI wanders off-story, contradicts itself, breaks immersion the moment a player asks something unexpected.
2. **Too rigid** — choose-your-own-adventure mode. The author scripts every line. Works at small scale, collapses when players improvise.

GALDR's answer is a strict separation of concerns: the dramatist controls *structure*, the AI controls *language*. Neither touches the other's domain.

---

## Technical Design Patterns & Observability

To meet the **p95 < 500ms** latency target while maintaining a clean, testable codebase, GALDR employs several key architectural patterns:

### 1. Inversion of Control (IoC) & Dependency Injection
The `GaldrEngine` does not depend on concrete implementations of AI services (OpenAI, local models, etc.). Instead, it depends on **Protocols** (`LLMService`, `TTSService`).
- **Why?** This allows for instant "Service Swaps" (e.g., using a local Llama-3 for speed vs. GPT-4o for quality) and enables **deterministic testing** without hitting expensive APIs.

### 2. Telemetry-First Design
Every step of the 8-step orchestration loop is measured using high-precision timers. 
- `EngineResponse` returns a `step_latencies` map.
- A custom `TelemetryMiddleware` tracks end-to-end request time and logs warnings for any request exceeding the 500ms budget.
- This data is crucial for identifying bottlenecks (is it the LLM generation? the STT transcription? or just Python's event loop overhead?).

### 3. Strict State Machines
`GameState` is a Pydantic v2 model with `extra="forbid"` and `validate_assignment=True`. 
- Every mutation is validated at write-time. 
- The state is the **Single Source of Truth**. The engine is stateless; you can reconstruct a session's entire reality just by reloading its `GameState` JSON.

---

## The 8-step orchestration loop

`engine.process_input()` runs in a fixed order. The order isn't arbitrary:

```
1. GPS check
2. Intent matching
3. Skill check (if required)
4. State mutation
5. Node transition
6. Prompt construction
7. LLM generation
8. Content filter → TTS
```

**Why GPS first?** Reverb parameters need to be ready before TTS at step 8. Calculating proximity early also allows geo-context to feed into the prompt at step 6.

**Why intent matching before skill checks?** Intent matching tells us *which action* the player is attempting. The action definition carries the skill check type and DC. You can't resolve the mechanics before knowing what's being attempted.

**Why skill checks before the LLM?** The dice result is semantic input to the prompt — the AI narrates an outcome, not a process. "You rolled a 17 against DC 15, with a 3-point margin" becomes "you barely managed it, describe the near-failure". If we generated first and checked dice after, the AI would have to be retroactively edited.

**Why state mutation before prompt construction?** The prompt includes inventory, HP, flags, and world state. It needs to reflect the *post-action* state, not the state from before the player acted.

**Why content filtering after LLM?** Pre-filtering happens in the prompt (forbidden topics, character constraints). Post-filtering catches anything that slipped through and applies length limits. Running both before and after the LLM would be redundant and slow.

---

## State-first design

`GameState` is a Pydantic model. Everything that changes the world — consequences, node transitions, inventory — goes through methods on `GameState` or `NarrativeFlags`. There's no direct dict manipulation.

This matters because:

- Invalid state is caught at write time, not at read time
- The full state is serialisable to JSON at any point (session persistence is trivial)
- Tests can construct any state precisely without mocking
- The agentic loop can be replayed deterministically for debugging

The tradeoff: Pydantic adds overhead on every mutation. At GALDR's scale (single-player sessions, <2s response budget) this is irrelevant.

---

## Intent matching

Offline (no LLM): numeric selection (1/2/3) → exact action ID → fuzzy word overlap with starts-with stemming → yes/no heuristics. This priority order reflects how players actually interact: most reach for numbers first, then keywords.

Online (with LLM): a small constrained prompt asks the model to return an action ID from the available list. Cheaper than full generation, fast, and falls back to offline matching if it fails.

The two-tier approach means the engine is always playable. Losing API connectivity degrades response quality, not game functionality.

---

## Skill checks and narrative quality

`dice.py` implements D&D 5e-style resolution: d20 + ability modifier vs difficulty class. Results map to five narrative tiers: *spectacular*, *solid*, *narrow*, *failure*, *disaster*. These tiers go into the prompt — the AI doesn't receive raw numbers, it receives directorial language.

Natural 20 and natural 1 are treated as special cases regardless of modifiers. A natural 20 from a character with -3 charisma still produces a spectacular outcome — the dice gods intervened. This is a deliberate theatrical choice, not a simulation fidelity choice.

---

## Guardrails

Two layers:

**Layer 1 — Prompt-level (pre-generation).** The system prompt includes forbidden topics per node. This shapes generation before it starts and is cheap.

**Layer 2 — Filter-level (post-generation).** `ContentFilter` runs regex patterns against the generated text. Global hard blocks (self-harm, sexual violence against minors) apply everywhere. Per-node topics apply only in the relevant scene — "religion" might be forbidden in a secular urban narrative but fine in a medieval fantasy.

The split exists because prompt instructions are probabilistic (the LLM can ignore them) while regex is deterministic. Hard safety requirements need the deterministic layer.

---

## Voice and geofence

`VoiceParams` on each node defines pitch shift, tempo, emotion, and reverb level. These are passed to TTS at generation time. In the PoC, these map to OpenAI TTS voice selection and speed. In production, they'll drive the custom neural model trained on the voice actor's recordings.

`geofence.py` calculates Haversine distance to each node's GPS anchor. Proximity feeds two things: a narrative context string injected into the prompt ("the player is 12m away, approaching — build tension"), and the reverb parameter passed to TTS. Linear reverb falloff was chosen over exponential because outdoor performance is unpredictable and linear is easier to tune during field testing.

---

## What's deliberately missing

**No database yet.** `repository.py` has an in-memory store and a file-based store. PostgreSQL is the production target but adding it before the scenario content is stable would be premature.

**No authentication.** Sessions are identified by UUID. For the Ekokammaren pilot, single-device use in a supervised context, this is fine. An auth layer would sit in FastAPI middleware and not touch the engine.

**No streaming LLM responses.** The TTS pipeline currently waits for the full generated text before synthesising. Streaming text → chunked TTS is the obvious latency improvement for production, but it adds significant complexity to the WebSocket protocol and wasn't worth it for the PoC.

**GALDR Studio (the visual node editor)** isn't built yet. The JSON scenario format was designed to be the target format for a node-based GUI — the data model is stable, the editor is Year 2.
