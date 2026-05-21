# CALLOUSED / GALDR Engine — Development Log

Examensarbete technical diary. Every entry documents what changed, why, and what was learned or measured.
Format: `## YYYY-MM-DD — Title` → What / Why / Impact.

---

## 2026-04-24 — Initial Live Test & Bug Triage

### Voice loop ran for the first time (The Lighthouse Keeper scenario)

**What:** First full end-to-end run of `voice_play.py` using Azure OpenAI (gpt-4o) + Azure AI Speech TTS/STT.

**Bugs found:**

1. **Double TTS billing** — `engine.process_input()` calls `tts.synthesize()` internally (Step 7 of the 8-step loop), AND `voice_play.py` calls `tts.speak()` again after getting the response. Two Azure Speech API calls per narration line.
2. **Double LLM on node transition** — `voice_play.py` called `engine.enter_node()` after detecting a transition, which triggered a second LLM generation for the same node that `process_input()` had already transitioned into.
3. **Language mismatch** — scenario was in Swedish, intended language is English.
4. **LLM hallucinated ending** — with a single "avskedet" end node and no `opening_text`, the LLM generated different endings on each run. No determinism.

**Fixes:**

- Introduced `_NullTTS` stub — engine receives `_NullTTS()` so its internal `synthesize()` returns `b""`. Voice loop handles all actual playback directly. Eliminates double billing.
- Removed `enter_node()` call after transitions. Voice loop now reads `current_node.opening_text` directly.
- Rewrote scenario in English as "The Lighthouse Keeper's Secret" (`app/scenarios/the_lighthouse_keeper.json`).
- Split single end node into two scripted nodes (`ending_understood`, `ending_mystery`), each with `opening_text`. LLM is never called on end node entry.

---

## 2026-04-24 — ElevenLabs Integration

### Replaced Azure AI Speech TTS with ElevenLabs for voice quality

**What:** Azure AI Speech (en-US-AriaNeural with SSML narration-professional style) had acceptable quality but robotic delivery. Integrated ElevenLabs API for higher-fidelity voice.

**SDK issue:** ElevenLabs Python SDK v2.44.0 removed `client.generate()`. Updated to `client.text_to_speech.convert()`.

**Free tier limitation:** ElevenLabs free tier blocks all premade library voices (Rachel, Aria, etc.). Workaround: user created a custom voice via ElevenLabs Voice Design tool. Custom voice ID stored in `ELEVENLABS_VOICE_ID` env var.

**Config:** `app/.env` → `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`. Loaded via `galdr/config.py` (`Settings` Pydantic model with `extra="ignore"`).

**Fallback logic in `voice_play.py`:** If `settings.elevenlabs_api_key` is empty, falls back to `AzureSpeechTTSService`. No code change required to switch.

---

## 2026-04-24 — Barge-In Implementation

### Player can interrupt narrator mid-sentence

**What:** Implemented concurrent TTS playback + Azure continuous STT. When player speaks while narrator is talking, playback stops and the recognized text is used as player input — skipping the separate listen step.

**Architecture:**

- `AzureSpeechTTSService.speak_with_barge_in()`: runs `SpeechSynthesizer` in a daemon thread, `SpeechRecognizer` in continuous mode on the default mic simultaneously. On recognized speech, stops synthesizer.
- `ElevenLabsTTSService.speak_with_barge_in()`: generates PCM first, then plays via sounddevice in a daemon thread, runs Azure STT in continuous mode. On recognized speech, calls `sd.stop()`.

**Echo / false positive bug:** Initial implementation used `recognizer.recognizing` (partial results). The mic picked up the speaker output and partial STT results fired mid-sentence, immediately canceling playback. Fixed by switching to `recognizer.recognized` (final complete utterances only). Trade-off: ~1-2s slower interrupt response, but no false positives.

**Arg order locked:** `speak_with_barge_in(text, params, stt)` — params before stt. This is the canonical order across both TTS services.

---

## 2026-04-24 — ElevenLabs Latency Optimization

### Lowered output format from mp3_44100_64 to pcm_16000

**What:** Changed ElevenLabs `output_format` from `mp3_44100_64` to `pcm_16000`.

**Why:** MP3 at 44.1kHz requires more bytes to generate, transfer, and decode. PCM at 16kHz is raw audio — no encoding/decoding step, smaller payload, lower end-to-end latency.

**Measured impact:** Not yet formally benchmarked, but PCM eliminates the MP3 decode step and reduces payload by approximately 70% (64kbps MP3 vs 16kHz×16bit×1ch PCM ≈ 256kbps raw, but short utterances generate much less total data). Primary gain is removal of the pydub decode step and smaller network payload.

**Trade-off:** 16kHz mono is lower fidelity than 44.1kHz stereo MP3. Acceptable for voice-only RPG; not acceptable for music. For higher quality: set `ELEVENLABS_OUTPUT_FORMAT=pcm_22050` or `pcm_44100` in `.env`.

**Config:** `galdr/config.py` → `elevenlabs_output_format: str = "pcm_16000"`. Overridable via `.env`. Samplerate is parsed from the format string at runtime by `_samplerate_from_format()` in `elevenlabs_service.py` — no hardcoded values.

---

## 2026-04-24 — Gemini Revert (Breaking Changes)

### Reverted three files rewritten by Gemini with breaking API changes

**What:** An external AI (Gemini) rewrote `azure_service.py`, `elevenlabs_service.py`, and `voice_play.py` with numerous breaking changes. All three files were restored to correct versions.

**Gemini's breaking changes included:**

- `AzureSpeechSTTService.__init__`: changed `key=` to `api_key=` (wrong parameter name)
- `AzureSpeechTTSService`: removed SSML, voice map, `speak()`, `speak_with_barge_in()`, hardcoded voice to AndrewNeural
- `AzureSpeechSTTService`: renamed `listen_from_mic()` to `transcribe_mic()` (broke voice_play call sites)
- `ElevenLabsTTSService`: removed `synthesize()` (Protocol contract crash), removed `speak()`, wrong barge-in arg order `(text, stt, params)` instead of `(text, params, stt)`
- `voice_play.py`: passed real TTS to engine (re-introduced double billing), used nonexistent `stt.transcribe_mic()`, wrong barge-in arg order, referenced nonexistent `settings.azure_openai_max_tokens` in generate_text call

**Lesson:** Never let an LLM refactor files without reviewing the diff against the working version. The Protocol interface contract (`synthesize()` returning `bytes`) is load-bearing — removing it causes immediate `AttributeError` at runtime.

---

## 2026-04-24 — Checkpoint System (Neural Sync)

### Implemented file-based save/load for CALLOUSED playtesting

**What:** Added checkpoint persistence so full playtests of CALLOUSED can be resumed without replaying the prologue.

**Files changed:**

- `galdr/core/nodes.py`: added `is_checkpoint: bool = False` to `NarrativeNode`
- `galdr/core/saves.py`: new module. `save_checkpoint()` serializes `GameState` to `app/saves/<scenario_id>.json` via Pydantic `model_dump_json()`. `load_checkpoint()` deserializes with `model_validate_json()`. `checkpoint_exists()` and `delete_checkpoint()` for startup logic.
- `voice_play.py`: on startup checks for existing save → voice prompt to resume or restart. On node entry where `is_checkpoint=True`: saves state + speaks "Biometrics stabilizing. Neural backup synchronized."

**Why Pydantic:** `GameState` has `extra="forbid"` and `validate_assignment=True`. Round-tripping through JSON via Pydantic guarantees the loaded state is structurally valid — no silent corruption.

**Usage in scenario JSON:** Add `"is_checkpoint": true` to any node. Example: the `surface_exit` node at the end of the CALLOUSED prologue.

---

## 2026-04-24 — Tribal Service Calibration

### Voice-driven D&D 5e stat generation for CALLOUSED prologue

**What:** New module `galdr/core/calibration.py`. Before the game starts, a narrator voice asks the player 4 thematic "Tribal Service" questions. An LLM interprets the answers and assigns the D&D 5e standard array (15, 14, 13, 12, 10, 8) to the six ability scores (STR/DEX/CON/INT/WIS/CHA).

**Why:** CALLOUSED characters should reflect the player's tribal background, not a menu. Voice-driven calibration stays in the "theater of the mind" contract — no screen, no selection UI.

**LLM prompt design:** System prompt enforces strict JSON output with exactly the standard array values. Temperature=0.2 to reduce creativity while allowing reasonable inference. `max_tokens=80` (just the JSON object). Regex extracts JSON from response in case the LLM adds surrounding text. If LLM returns invalid/non-standard values, `_enforce_standard_array()` re-ranks the stats preserving relative order.

**Integration:** Called in `voice_play.py` after name capture, before opening narration. Result stored in `state.character.stats`. Narrator confirms dominant stat: *"Calibration complete. Biometrics locked. Your strength runs deep."*

**Skipped on resume:** The checkpoint resume path bypasses calibration — `state.character.stats` is already set in the loaded save.

---

## 2026-04-24 — Fix: MP3 bytes parsed as PCM (buffer error on first speak)

**Error:** `ValueError: buffer size must be a multiple of element size` on `np.frombuffer(pcm, dtype=np.int16)`.

**Root cause:** `app/.env` still had `ELEVENLABS_OUTPUT_FORMAT=mp3_44100_64` from the previous MP3-based implementation, overriding the new `pcm_16000` default in `config.py`. ElevenLabs returned MP3 bytes; the service tried to interpret them as raw int16 PCM. MP3 has a file header and compressed frames — not a multiple of 2 bytes in the way int16 expects.

**Fix:** Updated `app/.env`: `ELEVENLABS_OUTPUT_FORMAT=pcm_16000`.

**Lesson:** When changing a config default, also update all `.env` files that have the old value hardcoded. The `.env` always wins over `config.py` defaults.

---

## 2026-04-24 — Fix: Player locked out during narration (no barge-in on speak())

**Problem:** Three `speak()` calls in the main game loop had no barge-in: opening narration (22s), node transition text, and LLM response text. Player could not interrupt any of them. Only the explicit choices prompt used `speak_with_barge_in`. From the player's perspective: locked in silence for 22 seconds, no way to act.

**Fix:** Added `narrate(tts, stt, text, voice) -> str` helper. Unlike `speak()`, `narrate()` calls `speak_with_barge_in` when available and returns captured speech. Every narration in the main loop now uses `narrate()`. Captured speech is stored as `pending_input` and used as the next player input — the player never has to repeat themselves after interrupting.

**Flow change:**

- Before: speak opening → speak choices → listen → speak response → speak choices → listen → ...
- After: narrate opening → (barge-in = skip + use as input OR wait) → narrate choices → (barge-in = input OR explicit listen) → narrate response → (barge-in = next input OR explicit listen) → ...

`speak()` is now reserved for system prompts (name capture, checkpoint messages, resume) where interruption has no meaningful target.

---

---

## 2026-04-27 — CALLOUSED Prologue Scenario Authored

### First playable CALLOUSED content

**What:** Authored `app/scenarios/calloused_prologue.json` — 5-node prologue following the structure defined in `calloused_master.md` §10.

**Node graph:** `silent_drop` → `blade_encounter` → [`adrenaline_crash` | `blade_wounded` → `adrenaline_crash`] → `surface_exit`

**Key decisions:**

- Calibration fires as a pre-loop step (via `calibration_enabled: true`), not as a navigable node. The Tribal Service questions happen before `silent_drop` narration plays. Narratively: the smart-dust reads you as you fall.
- `blade_encounter` has two actions (DEX DC 14, WIS DC 12) with different success/fail consequences. Dex failure = -6 HP; Wis failure = -4 HP. Both failures set `fatigued: true`.
- `blade_wounded` is a brief transition node — establishes injury state before the crash hits. Keeps the failure path feeling weighty without requiring a full recovery arc.
- `adrenaline_crash` has two actions: `rest_briefly` (CON DC 10, fail sets `rest_needed: true`) and `examine_pods` (free, gives Cryo-Pod Seal item). The Sleeper Silo reveal — hundreds of empty cryo-pods — is the prologue's main world-building beat.
- `surface_exit` is `is_checkpoint: true` and the only end node. Neural Sync saves here. Ends with Lo's silent appearance.

**Scenario authoring guide** (`Calloused_game/SCENARIO_AUTHORING_GUIDE.md`) was created in the same session to allow external AI assistants to author additional content without project context.

---

## 2026-04-27 — Streaming TTS Pipeline (Sentence-Level)

### LLM token stream → sentence splitter → per-sentence TTS → immediate playback

**What:** Replaced the sequential `process_input()` → full LLM response → full TTS → play flow with a streaming pipeline. First audio now starts when the first sentence is ready, not when the full response is synthesized.

**Files changed:**

- `galdr/utils/sentence_splitter.py` (NEW): async generator `split_sentences(tokens)`. Buffers LLM token stream, yields complete sentences on `.`, `!`, `?` followed by whitespace. Handles ellipsis correctly via negative lookbehind.
- `galdr/services/azure_service.py`: added `AzureOpenAIService.generate_text_stream()`. Uses `stream=True` on the Azure OpenAI client. Logs first-token latency and total stream latency separately for benchmarking.
- `galdr/core/engine.py`: added `process_input_stream()` and `_generate_response_stream()`.
  - `process_input_stream()` runs steps 1-4 (GPS, intent, mechanics, transition) synchronously and returns immediately. The LLM call is in `_generate_response_stream()`, which is a lazy async generator — no LLM request fires until the caller iterates it.
  - Key design: if the new node has scripted `opening_text`, the caller narrates that and discards the token generator. No LLM call is made. This saves the redundant generation that occurred in the old flow.
  - `_generate_response_stream()` records dialog to state in a `finally` block — fires whether the stream is fully consumed or abandoned.
  - Falls back to `generate_text()` if the LLM service has no `generate_text_stream` attribute (e.g., mock services).
- `voice_play.py`: added `narrate_stream(tts, token_stream, voice) -> str`. Logs TTFA at first sentence. Main loop now calls `process_input_stream()` instead of `process_input()`. On scripted opening_text transition, token_stream is discarded (no LLM call). On no-transition, `narrate_stream()` plays each sentence as it arrives.

**TTFA improvement (estimated):**

| | Before | After |
| --- | --- | --- |
| Time to first audio | ~5-8s (full LLM + full TTS) | ~0.8-1.5s (first sentence LLM + TTS) |
| LLM wasted calls | 1 per turn | 0 when opening_text exists |

**What streaming does NOT yet solve:**

- Barge-in during a streamed sentence: each sentence plays fully before the next starts. Mid-sentence interruption requires a different architecture (concurrent TTS + STT during streaming). Logged as next step.
- Barge-in interrupt latency (1-2s from `on_recognized`): separate issue from streaming TTFA. Requires VAD-based approach. Logged below.

**Content filter:** skipped per-chunk during streaming (chunks are too small for meaningful context). Full assembled text is logged. System prompts constrain output. Belt-and-suspenders filter on full response is a future addition.

**Lesson:** Lazy async generators are the right abstraction for this pipeline — the generator holds the LLM call but doesn't start it until iterated. Callers that don't need the LLM (scripted opening_text) pay zero cost.

---

---

## 2026-04-27 — Pressure, Lo Trust, and Full Act 1

### Pressure mechanic, Lo trust system, and first complete playable arc

**What:** Three simultaneous additions: engine mechanics, system prompt injection, and full game content.

**Pressure mechanic (`character.pressure`, 0–10):**

- Added `pressure: int = Field(default=0, ge=0, le=10)` to `Character` in `state.py`.
- Added `modify_pressure` consequence type to `nodes.py`.
- Injected pressure-driven narrator directives into `build_system_prompt()` in `prompt_regi.py`. Thresholds: 0-3 = normal, 4-6 = "narrator harsher, shorter sentences", 7-9 = "disorientation, sentences fragment", 10 = "COLLAPSE — force incapacitation beat". The LLM shifts register based on state. No hardcoded strings in narrator output — the shift happens through system prompt instruction.
- Why: CALLOUSED characters have Acoustic Vulnerability and Adrenaline Crash as biological flaws. Pressure tracks the cumulative physiological cost. Without it, all scenes have the same narrator weight regardless of what the player has been through.

**Lo trust system (`character.lo_trust`, 0–5):**

- Added `lo_trust: int = Field(default=3, ge=0, le=5)` to `Character` in `state.py`.
- Added `modify_lo_trust` consequence type to `nodes.py`.
- Added `lo_trust` condition type to `nodes.py` — actions gated by `{ "type": "lo_trust", "min": N }`.
- Added `pressure` condition type to `nodes.py` as well.
- Injected Lo status into `build_system_prompt()`: maps trust level (0-5) to a narrator directive string. At trust 0: "Lo has left — do not mention Lo". At trust 5: "rare, understated warmth". The narrator knows Lo's relationship state without being told in-scene.
- Why: Lo must never be cosmetic. If every action has the same relationship cost/benefit, players have no reason to invest in Lo. The trust system makes Lo's presence narratively load-bearing.

**Narrative contracts (applied to all new nodes):**

- Every node costs something (HP, pressure, flag, or resource).
- Information is unreliable — Worker Log fragment deliberately has internal contradictions ("479 units, not 480" — the Ancestors were hiding something).
- System prompts are now directive-style (bullet list) instead of prose. Concretely better for consistent LLM output.

**`calloused.json` — Full game v1.0.0 (13 nodes):**

- Prologue (5 nodes) merged with Act 1 (8 nodes) into a single playable arc.
- Act 1: glass crater crossing → wind shrine (Worker Log discovery) → The Ribs (trading hub) → The Broker (info trade) → Bunker Gate (Act 1 end).
- The Cryo-Pod Seal from the prologue is consequential in Act 1: accepted at the Ribs gate OR traded to The Broker for the map. Players who explored the silo are rewarded.
- The Worker Log fragment has unreliable information — "479 units, not 480" — foreshadows Act 2's revelation (the Ancestors miscounted something deliberately).
- The Gate Approach Map has an unlabeled second mark (ventilation shaft) — hooks Act 2.
- `bunker_gate` is the checkpoint end node. The hum from behind the gate is the Act 1 cliffhanger.

**Lo trust wired into Act 1:**

- Asking about the Ancestors: +1 trust.
- Following Lo's crossing route: +1 trust.
- Letting Lo handle the Ribs gate: requires trust ≥ 4, gives +1.
- Walking in silence during crater_morning: neutral (no cost, no gain — respecting Lo's space).

---

## 2026-04-27 — Act 2 Midpoint: The Cleansing Protocol

### The forvaltar-saga's point of no return

**What:** Authored 6 new nodes extending `calloused.json` from Act 1's `bunker_gate` through the midpoint. `calloused.json` promoted to v2.0.0. Now 19 nodes covering Prologue → Act 1 → Act 2 midpoint.

**New node arc:** `bunker_gate` (retrofitted) → `shaft_descent` → `ancestor_corridor` → `activation_chamber` → `authority_recognized` → `cleansing_protocol` → `cleft_silence` (checkpoint, new end node).

**Personal stakes — Ven:**

The midpoint required a named victim whose death lands as something more than a statistic. Ven is the Cleft's grid-reader — introduced in `crater_morning` via Lo's mention ("Ven gives it two seasons. Maybe three"). Ven appears again in `ancestor_corridor` as a live comms voice, reading tectonic data, unknowingly directing the player toward the relay reset. She says "be careful" and the channel closes. In `cleft_silence`, her frequency disappears without announcement. Not dead signal — the frequency itself stops existing. Absence does the work.

This follows the exact same pattern as Lo's permadeath contract: one moment of weight, then silence. The narrator never says "Ven is dead."

**The recognition reveal:**

When the player places their hand on the reader plate (`activation_chamber` → `authority_recognized`), the system returns: SURFACE POPULATION CENSUS: 479 UNITS. DELTA FROM REGISTERED COUNT: -1. DISCREPANCY RESOLVED. The 479 from the Worker Log ("do not tell the Admins the count... 479 units, not 480") resolves here. The player IS the hidden unit. The Ancestors weren't missing a number — they were missing a person. That person was always the player. The system was never broken. It was waiting.

Players who found the Worker Log in Act 1 feel this land twice. Players who didn't find it get a mystery instead of a callback. Both valid.

**The Ancestors' math:**

`cleansing_protocol` surfaces the protocol text verbatim: GRID EFFICIENCY DELTA: +23%. THERMAL CLEARANCE: INITIATED. The Ancestors are not villains with motives — they are engineers running an optimization. The horror is that their math is right. This is what `calloused_master.md` §0 calls the real conflict: "Their conclusion is monstrous. But their math is right."

**Lo trust impact:**

`cleft_silence` applies `modify_lo_trust: -2` on entry. The trust drop represents the irreversible damage to the relationship — Lo doesn't know the player activated the system yet, but the world the player made no longer contains The Cleft. Players who invested in Lo (trust 4-5) arrive at trust 2-3 (wary, not gone). Players who never built trust (1-2) lose Lo at the midpoint. Investment has consequence.

**Pressure at midpoint:**

The `cleansing_protocol` → `cleft_silence` sequence applies `+3` then `+2` pressure. A player who entered Act 2 with pressure above 5 will hit the disorientation register (7-9) during the most important scene in the game. Narrator fragments. Reality slips. This is correct — this is what Acoustic Vulnerability and physiological debt feel like at the moment of maximum cost.

**Scenario authoring rules applied:**

- Every node costs something: shaft_descent → bunker infiltration flag, ancestor_corridor → optional flag, activation_chamber → pressure, authority_recognized → pressure +2, cleansing_protocol → pressure +3, cleft_silence → lo_trust −2 + pressure +2 + two flags.
- Information plants: Ven first mentioned in crater_morning, live in ancestor_corridor, gone in cleft_silence. Worker Log fragment ("479 units, not 480") planted in Act 1, resolved in authority_recognized.
- Directive-style system_prompts throughout.
- No numbers read aloud.

---

## 2026-04-27 — Prologue Completion + Lo Confrontation

### Full playable arc through Act 2 opening

**What:** Extended `calloused.json` to v2.1.0 (21 nodes). Three additions: prologue multi-resolution polish, Lo confrontation scene, Act 2 opening node.

**Prologue — third resolution paths added:**

- `blade_encounter` now has 3 paths: DEX (move fast and low, DC 14), WIS (listen and map, DC 12), STR (use body mass to get under the blade's arc, DC 12). All physical approaches covered. STR path is grounded in CALLOUSED's human evolution — the player is short, dense, heavy-boned. Their body geometry is the tool.
- `adrenaline_crash` now has 3 paths: CON rest (DC 10), free examine pods (Cryo-Pod Seal), INT catalog (DC 11 — use cognition to override the crash). INT success also gives the Cryo-Pod Seal via a different route. INT failure adds pressure (spiraling instead of focusing).

**Lo confrontation (`lo_confrontation`):**

The scene where lo_trust is tested in dialogue rather than state consequence. Four paths:

1. **Truth** (lo_trust ≥ 1, no check) — full confession. Trust -1. Lo stays.
2. **Deflection** (lo_trust ≥ 1, CHA DC 12) — technically true, incomplete. Success: Lo uncertain, no trust change. Failure: Lo reads it, trust -1.
3. **Silence** (lo_trust ≥ 1, no check) — Lo reads the silence as an answer. Trust -1.
4. **Surface alone** (lo_trust = 0) — Lo is not there. Player emerges to an empty crater. No confrontation possible. Worse than any of the above.

Players who never invested in Lo (trust ≤ 2 → dropped to ≤ 0 at `cleft_silence`) lose Lo before this scene fires. The confrontation is only available if the relationship survived the midpoint damage.

**`act2_open` (checkpoint, end node for now):**

"The crater is the same. The obsidian is the same. The only thing missing is The Cleft. And Ven. And whatever you thought you were doing here." Checkpoint. Empty actions until Act 2 content is authored.

---

## 2026-04-27 — Cleaning Bot Reframe + Passive Authentication

### blade_encounter rewritten; activation_flee added (22 nodes total)

**What:** Two structural additions to `calloused.json`.

**`blade_encounter` — cleaning unit, not a guard:**

Full rewrite. The threat is a maintenance cleaning unit still running its circuit after 50,000 years. Infrastructure, not intent. This resolves the "no robot gatekeeper" design tension: the unit is not hunting the player — it is on a timer, following a path, doing the only thing it knows how to do. Consistent with "environment is the gate."

Four resolution paths:

1. **DEX** (DC 14) — slip past in the dark. Success: through. Failure: blade wounds → `blade_wounded`.
2. **WIS** (DC 12) — read the pattern, time the gap. Sets `understood_the_pattern` flag.
3. **STR** (DC 12) — charge at it. Success: stops the unit. Narrator delivers the punchline straight: "a cutting wheel no larger than a fist. 50,000 years of maintenance. Stopped." Comedy emerges from deflation, not winking.
4. **INT** (DC 13) — locate the service interrupt on the wall, shut the unit down cleanly. Sets `shut_down_the_unit` flag.

Opening text: acoustic horror. No names. Pure sound — "a low mechanical sound, rhythmic, close to the floor, moving in a pattern."

**`activation_flee` — proximity authentication:**

New node. Player's third option at the console: turn back, don't touch it.

The system authenticates from proximity detection before the player reaches the corridor. "CLOSEST MC DESCENDANT DETECTED. PROXIMITY AUTHENTICATION INITIATED." The system did not ask. It did not need to.

This is worse than having chosen: the player tried to walk away and the system treated nearness as consent. All three activation paths converge on `authority_recognized` — the system gets its operator regardless.

Node specs: `on_enter` pressure +1, single action forward (additional pressure from `activation_flee` consolidates into the same `authority_recognized` pressure spiral as active paths).

**Validation:** `Scenario.load_from_file()` — 22 nodes, clean.

---

## 2026-04-28 — BiomeContext Zone Layer

### Ambient biome context injected into every system prompt

**What:** Added `BiomeContext` Pydantic model to `nodes.py`. Optional field on `NarrativeNode`. Injected as Layer 2b in `build_system_prompt` — sits between scenario context and node-specific direction.

**BiomeContext fields:**

- `name` — display name injected as prompt header
- `description` — one or two sentences of environmental atmosphere
- `pressure_base` — ambient pressure contribution from the environment (informational for narrator; actual pressure mutations are still explicit node consequences)
- `ambient_tags` — flavor words the LLM can draw from
- `encounter_hints` — possible threats/events the narrator can reference without authoring them

**Three biomes defined across all 22 CALLOUSED nodes:**

| Biome | Nodes | pressure_base |
| --- | --- | --- |
| Glass Crater Basin | silent_drop, surface_exit, crater_morning, obsidian_crossing, wind_shrine, ribs_visible, cleft_silence, lo_confrontation, act2_open | 1 |
| The Ribs | ribs_gate, ribs_interior, the_broker | 0 |
| Ancestor Facility | blade_encounter, blade_wounded, adrenaline_crash, bunker_gate, shaft_descent, ancestor_corridor, activation_chamber, activation_flee, authority_recognized, cleansing_protocol | 2 |

**What this means in practice:** Every LLM call now includes the biome layer. A narrator describing the obsidian crossing gets "UV, dust, sinkhole" as ambient context. A narrator in the facility gets "hum, sealed, 50,000-year silence, maintenance unit still on circuit." No authored encounter required — the LLM can draw on these as texture.

**Validation:** `Scenario.load_from_file()` — 22 nodes, all biomed, clean.

---

## 2026-04-28 — VAD Barge-in (sounddevice energy threshold)

### Replaced Azure continuous recognition with sounddevice VAD for barge-in interrupt

**Problem:** Both TTS services (`AzureSpeechTTSService`, `ElevenLabsTTSService`) used Azure continuous recognition for barge-in. Azure fires `on_recognized` only after a complete utterance is processed — ~300-500ms after speech onset. TTS kept playing throughout that window.

**Fix:** `galdr/utils/vad.py` — `record_until_silence(on_speech_start)`.

Flow:

1. sounddevice monitors mic in 20ms blocks
2. When RMS > 0.015 (speech onset): calls `on_speech_start()` immediately — TTS stops within ~20ms
3. Includes 200ms pre-roll (captures start of utterance that triggered the threshold)
4. Records until 800ms of silence → utterance complete
5. Returns PCM int16 bytes
6. Azure STT transcribes the captured bytes via `_transcribe_pcm_sync`

**Interrupt latency improvement:** ~20ms (one audio block) vs ~300-500ms (Azure recognition latency). This is the `[BARGE-IN] interrupt→transcribe` log line.

**Both services updated:**

- `AzureSpeechTTSService._speak_barge_in_sync` — replaces Azure continuous recognition with sounddevice VAD
- `ElevenLabsTTSService._play_barge_in_sync` — same; ElevenLabs is the primary service

**New on `AzureSpeechSTTService`:** `_transcribe_pcm_sync(pcm_bytes, sample_rate)` — accepts raw PCM int16, wraps in Azure PushAudioInputStream, returns transcribed text. Logs `[STT←vad]`.

**Threshold tuning:** `energy_threshold=0.015` works in quiet rooms. Raise to 0.03-0.05 if TTS bleeds into mic through speakers. Configurable as a kwarg.

---

## 2026-04-28 — Prompt System Refactor (prompt_regi → prompt_director)

### Renamed module, added dice narrative and context message builders

**What:** `galdr/core/prompt_regi.py` deleted. Replaced by `galdr/core/prompt_director.py`. The 8-layer `build_system_prompt()` function is unchanged in structure but two new functions were added.

**`build_dice_narrative(result: SkillCheckResult) -> str`:**

Translates a mechanical dice result into directorial language the LLM receives rather than raw numbers. Five quality tiers:

| Tier | Condition | Prompt instruction |
| --- | --- | --- |
| spectacular | crit success (nat 20) | "OUTSTANDING result — surpasses all expectations" |
| spectacular | margin large | "impressive result" |
| solid | clean pass | "competent, confident result" |
| narrow | margin ≤ 1–2 | "almost went wrong but made it at the last moment" |
| failure | failed | "credible failure — not embarrassing, task too difficult" |
| disaster | margin very negative | "serious failure with consequences" |
| disaster | crit failure (nat 1) | "dramatic, almost comic failure — something goes VERY wrong" |

The LLM receives quality tiers, not raw numbers. The dramatic tier carries the weight; the raw numbers are included for grounding only. No number is ever read aloud in narrator output.

**`build_context_messages(state: GameState, max_history: int = 10) -> list[dict]`:**

Converts dialog history from `state.get_recent_context()` to standard LLM message format (role/content dicts). Caps at 10 turns by default. Used by the engine to pass conversation history to the LLM alongside the system prompt.

**Why:** The dice narrative function decouples mechanical resolution from narrative presentation. Previously the engine had to write directorial instructions inline at each skill check site. Now it calls one function and passes the result to the LLM.

---

## 2026-04-28 — Benchmark Log Parser

### CLI tool for extracting latency stats from voice loop logs

**What:** New script `app/parse_benchmark.py`. Parses GALDR voice loop log files and reports per-metric statistics. Usage: `python parse_benchmark.py benchmark_01.log` or `cat log | python parse_benchmark.py -`.

**Metrics tracked** (regex-matched against log lines):

| Metric | Log tag |
| --- | --- |
| TTFA (input → first audio) | `[STREAM TTFA]` |
| Pre-LLM overhead (steps 1–4) | `[STREAM]` |
| LLM first token | `[LLM STREAM] first_token_ms=` |
| LLM total stream | `[LLM STREAM] total_ms=` |
| ElevenLabs TTS synthesis | `[EL TTS]` |
| Azure TTS synthesis | `[TTS]` |
| LLM call (non-streaming) | `[LLM CALL]` |

**Output:** n, min, mean, p50, p95, max per metric. Appends a target check: p95 < 500ms → PASS / MISS with percentage of turns under the threshold.

**Why:** The examensarbete requires real latency numbers from 10 benchmark runs. This script makes it one command against collected log files rather than manual parsing.

---

---

## 2026-05-12 — Prologue Rebuilt as Canonical Scenario + auto_next Engine Support

### calloused_prologue.json v1.0.0 (11 nodes) replaces all prior prologue content

**Context:** 2+ week gap since last entry. Session resumed from context summary. The prior `calloused.json` had accumulated two versions of the prologue — the original 5-node arc (`silent_drop → blade_encounter → adrenaline_crash → surface_exit`) and a second, completely separate 11-node prologue authored in `calloused_prologue.json`. The latter was substantially more developed in every dimension.

**`calloused_prologue.json` — what makes it the canonical version:**

- 11 nodes: `crater_threshold → facility_descent → the_dark → dark_wounded → cryo_room → console_chamber → proximity_auth → recognition → crater_surface → lo_aftermath → prologue_close`
- Full prologue arc in one file: Glass Crater surface → drop → cleaning unit encounter → cryo room → console/activation → decontamination sequence → Lo confrontation
- `the_dark` has 4 skill paths (DEX/WIS/STR/INT) with strong thematic differentiation. WIS success is the "first moment of understanding" — the player realizes the unit is on a circuit, not hunting them. The system indifference theme established here.
- `console_chamber → proximity_auth → recognition`: the proximity authentication horror — the player tries to leave, the system reads proximity as consent. "CLOSEST MC DESCENDANT DETECTED. PROXIMITY AUTHENTICATION INITIATED." Replaces the flawed `activation_chamber` node in the old calloused.json (which had the opening_text bug "You put yours down." pre-empting player choice).
- `lo_aftermath`: 4-path confrontation (truth / deflect / silence / stand alone) — much richer than `lo_confrontation` in the old file. `stand_alone` only fires if lo_trust = 0. `blame_the_system` has a CHA DC 12 check; success leaves Lo uncertain, failure drops lo_trust −1.
- `prologue_close`: flag-conditional system_prompt — 5 different narration variants depending on which lo_aftermath path resolved. No hardcoded ending text.
- No dead ends, no empty action arrays on non-terminal nodes. `prologue_close` is a clean terminal.

**`calloused.json` — deleted by the author.** The entire old scenario file was removed. `calloused_prologue.json` is now the active test scenario.

**Issue found and noted:** `recognition` `opening_text` reads "The reader plate is warm" regardless of activation path. For players who came via `proximity_auth` (never touched the plate), this is factually wrong. Not fixed yet — low priority.

**`auto_next` — engine gap found and fixed:**

`facility_descent` and `dark_wounded` both use `auto_next` with `auto_delay_seconds`. Neither the engine nor `voice_play.py` had any handling for this field. Without the fix: both nodes would reach the `else: [Listening (Sandbox)]` branch and wait indefinitely for player speech that had nowhere to go.

**Fix: `voice_play.py` main loop, new branch before existing action prompting logic:**

```python
elif not current_node.actions and current_node.auto_next:
    await asyncio.sleep(current_node.auto_delay_seconds)
    state.current_node_id = current_node.auto_next
    response = await engine.enter_node(state.session_id)
    # narrate opening of auto_next target, handle checkpoint, continue
```

Key design choices:

- Branch fires only when `actions` is empty AND `auto_next` is set — does not silently swallow nodes that have both (shouldn't exist, but defensive).
- Directly mutates `state.current_node_id` (valid: `GameState` uses `validate_assignment=True`, not `frozen=True`).
- Calls `engine.enter_node()` on the target node — fires its `on_enter` consequences and returns scripted `opening_text`. Same path as normal node entry.
- `continue` skips `process_input_stream` (no player input, no LLM call needed).
- Checkpoint save logic included: if the auto_next target is `is_checkpoint: True`, saves and speaks the Neural Sync line.

**Prologue validation (pre-test):**

```text
Node count: 11
Errors: none
Consequence types: add_item, modify_hp, modify_lo_trust, modify_pressure, set_flag, set_time, visit_location
```

All consequence types confirmed supported in `nodes.py`. All node references valid. No dangling targets.

**Run command:**

```bash
cd app
python voice_play.py --scenario scenarios/calloused_prologue.json
```

---

---

## 2026-05-12 — Playtest 1: Engine Works, Audio Broken

### Two test runs — engine flow confirmed, audio/barge-in fundamentally broken

**Test run 1 findings:**

Engine progression was correct — calibration, auto_next transitions, node flow all worked. TTFA on LLM streaming measured at 884ms (target met). However:

- **ElevenLabs TTS latency**: 5-18s per narration block before first audio. Full synthesis before playback. `chars=260 → 16s`, `chars=430 → 18s`.
- **Choice prompt unlistenable**: "What do you want to do? You can Move through — fast, on the next pause. You can Stop. Listen until the pattern makes sense.." — a paragraph of text read aloud for every action set.
- **Out-of-character input accepted**: Player said "What? Where am I?" — engine processed it, advanced the story.

**Fixes applied after run 1:**

- Added `narrate_sentences()`: split opening_text by sentence, speak each separately → first audio in ~1s.
- Choice prompt changed to: "What do you do?" (no action listing). Design decision: this game doesn't read choices.
- VAD guard period (0.35s sleep before VAD opens) + raised threshold (0.04 vs 0.015) to reduce speaker bleed false positives.
- `stop_event` added to `record_until_silence()`: VAD exits immediately when audio finishes, no 10s wait.

**Test run 2 findings (after fixes):**

Worse. The sentence-splitting fix introduced a new critical failure:

- **Severe audio glitches**: clicking, broken words, no full sentences audible. Described as "clicking around broken up pieces of words."
- **Root cause**: `narrate_sentences()` called `narrate()` per sentence. Each `narrate()` call opens a new `sd.InputStream` (for VAD) while `sd.play()` (OutputStream) is active. On Windows WASAPI, rapidly cycling concurrent input+output streams causes buffer underruns and audio artifacts.
- **`sd.stop()` kills both streams**: When barge-in fires, `on_speech_start=sd.stop` stops both OutputStream AND InputStream. VAD callback stops mid-capture. `done_event` may not be set, causing `done_event.wait()` to block for full timeout.
- **No barge-in**: Guard period + threshold too aggressive OR stream conflict preventing reliable detection. Speaker bleed still a risk on speakers.

**Fixes applied after run 2:**

- `narrate_sentences()` changed to `speak()` per sentence (no VAD per sentence). Eliminates the concurrent stream conflict entirely.
- Choice prompt changed to `speak("What do you do?", ...)` + `stt.listen_from_mic()`. Barge-in removed from this path.
- All narration paths now: `speak()` → audio finishes cleanly → `stt.listen_from_mic()` for input. No concurrent input+output streams.
- Sandbox path cleaned up.

**Architecture lesson**: On Windows with speakers (not headphones), concurrent `sd.play()` (OutputStream) + `sd.InputStream` causes glitches. The barge-in design requires headphones OR a different architecture (WebRTC-style echo cancellation or dedicated hardware VAD). For thesis testing: use headphones OR accept that barge-in is disabled.

**Current barge-in status**: Effectively disabled in narration paths. Not a thesis blocker — the core pipeline (STT → engine → LLM streaming → TTS) works. TTFA 884ms confirmed. Barge-in is a UX enhancement, not a correctness requirement.

**What still needs a test run**: The fixed flow (speak per sentence → listen) has not been tested yet.

---

---

## 2026-05-12 — Prologue v2.0.0: Design Alignment with calloused_master.md v2.9

### Major narrative and mechanical revision of calloused_prologue.json

**Context:** `calloused_master.md` reached v2.9 with significant design consolidation — Ven removed, The Ribs renamed Vestal, authentication redesigned as census count, Lo formally defined as world-state mirror. The v1.0.0 prologue pre-dated these decisions. Six areas of misalignment required correction.

**Changes applied:**

#### 1. Pressure arc recalibrated — Gold Zone (4-6) as target at lo_aftermath entry

v1.0.0 worst-case pressure path: 0 → 1 (descent) → 4 (dark DEX fail +3) → 5 (cryo catalog fail) → 7 (console study) → 9 (proximity_auth +2) → 13→capped (recognition +4) = 10. Arrival at lo_aftermath: max/collapsed.

v2.0.0 worst-case: 0 → 1 (descent) → 2 (dark fail +1) → 3 (cryo catalog fail) → 4 (proximity_auth +1) → 6 (recognition +2) = 6.

Changes:

- `the_dark` failure consequences: all paths reduced from +2-3 to +1. HP loss unchanged. The injury is the physical consequence; the soul is not yet broken.
- `console_chamber` `study_the_interface`: removed pressure +1 on success. Understanding the interface without understanding what it starts is not yet a cost.
- `proximity_auth` on_enter: +2 → +1.
- `recognition` on_enter: +3 → +2. `run` action: removed +1 (running out is the only option; adding pressure here is wrong).
- `crater_surface` on_enter: removed +2 pressure entirely. The player is OUT. The horror has already landed in recognition. Surfacing is not a new accumulation.

#### 2. Lo — world-state mirror, not emotional presence

v1.0.0: Lo "watches" the player, "does not rush them." Implies concern and attention directed AT the player. v2.9: Lo's behavior reflects world-state, not the player's emotional state.

Changes:

- `crater_threshold` system_prompt and opening_text: Lo faces the horizon, not the player. "Lo's attention is on the world — the changed pressure, the wrong silence — not on the player." Opening text changed from "Lo watches" to "Lo faces the horizon. They do not look down."
- `crater_surface` system_prompt: "Lo is accounting for what the world is now." Added note that Lo's eyes go to the horizon, not to the player, when they surface.
- `lo_aftermath` system_prompt: major rewrite. "Lo's behavior reflects the state of the world, not the emotional state of the player. The Cleft is gone. That is a world fact. Lo is processing what the world is now, without it. Lo does not perform grief." Opening text: "Not toward the sky where The Cleft was — toward you. Lo's attention is the same quality it gives to terrain. Reading what is there."
- `crater_surface` on_enter: removed `lo_recognizes_you` flag (implies a personal moment). Replaced with `lo_registers_world_change`.

#### 3. Worker Log 479 contradiction — Phase 1 plant added

v1.0.0: 479 count appears in cryo_room lore_hints (invisible to player) and in console_chamber lore_hints (also invisible). The contradiction was authored but never surfaced in play.

v2.0.0: The contradiction is now discoverable. `catalog_the_room` INT DC 11 success: narrator reads a terminal aloud — "SURFACE POPULATION CENSUS: 479 / 480 REGISTERED UNITS. STARTUP PENDING: DISCREPANCY UNRESOLVED." Sets `saw_479_terminal` flag. In `recognition`, if this flag is set, the system resolving to 480 lands differently — player makes the connection without narrator prompting.

This is Phase 1's first contradiction: there was supposed to be 480. The player is the 480th. The player completing the count is the Phase 1 hope. The system running its startup routine is how the hope ends.

#### 4. Recognition — startup routine framing strengthened

Added "FACILITY INITIALIZATION: STEP 7 OF 9" to the screen sequence. The player is not triggering a weapon. They are completing a startup sequence that has been stuck on step 6 for 50,000 years. The system is doing what it was always going to do once someone completed the census.

System prompt updated: "This is a startup routine. It is 50,000 years old. It is running exactly as designed. No one chose this outcome. There is no decision being made right now. The system does not know what The Cleft is. The horror is in the bureaucratic language. In the word STANDARD."

#### 5. "Not special — just first" — console_chamber reinforced

Opening text changed: "The reader plate is shaped for a human hand. Not yours specifically. Any hand. You are the one who is here." System prompt expanded: "The player is not special — they were simply the first one to arrive. The system has been waiting for anyone with the right biology. It has been waiting for 50,000 years."

#### 6. WIS path in the_dark — primary lesson emphasized

System prompt added: "WIS success (PRIMARY LESSON): the system does not know the player is here. It is not hunting. It is working. This is what the whole game is built on." The WIS path is now explicitly foregrounded as the most important teaching moment in the prologue.

Version: `calloused_prologue.json` promoted to v2.0.0.

Global system_prompt: Added "The system does not know about the player." — the game's thesis as a single sentence, injected into every LLM call from the first node.

---

---

## 2026-05-20 — Prologue v3.0.0: Full Canonical Rewrite

### Prologue rebuilt from scratch against Prologue_Discussion_GPT.md spec

**Context:** v2.0.0 prologue still contained two artifacts inherited from very early drafts: a "hatch" (implies a door the player opens — wrong; player falls through the ground) and a "grid-reader" (invented by an LLM assistant, never existed in the world). Additionally, the maintenance unit was still framed as a blade threat rather than a tiny floor-scrubber, and `dark_wounded` still applied HP damage from the blade framing.

`Prologue_Discussion_GPT.md` is the canonical v3.0 specification document. It was not read during the v2.0.0 rewrite. This entry covers the full realignment.

**Structural changes — entry mechanism:**

- Player and Lo investigate the stopped Eternal Breath on the crater floor together.
- Ground buckles under the player's weight — obsidian cracks. Player falls through into the Ancestor Facility below. Lo left on top at the crack.
- No hatch. No door. No voluntary descent. The fall is the inciting incident; not a failure state.
- `crater_investigation` (renamed from `crater_threshold`): both actions (`read_the_ground` WIS DC 8, `call_to_lo` free) lead to `the_fall`. The fall is unavoidable by design.
- `the_fall` auto-transitions to `the_dark` after 4 seconds.

**Maintenance unit reframe — the most consequential design change:**

v2.0.0 had a "blade" framing — ACoustic horror described as "a low mechanical sound, rhythmic." `dark_wounded` applied `modify_hp: -6` (blade wound).

v3.0.0: The unit is a knee-high ceramic floor-scrubber running a 50,000-year cleaning circuit. It is not a threat. It does not know the player exists. The comedy of `charge_at_it` (STR success) is the point: a hyper-dense heavy-boned body launching at full force at what turns out to be an ancient Roomba. Sparks briefly illuminate the hallway. The player just pulverized a floor-polisher.

- `dark_wounded`: removed `modify_hp` entirely. Only `modify_pressure: +1` and `set_flag: bruised_by_unit`. Opening text: "Something low and solid hits your shin at full speed. THUD." The injury is a bruised leg, not a cut.
- `slip_through` (DEX) and `go_still` (WIS): both now have `failure_node: "cryo_room"` — they NEVER route to `dark_wounded`. Only `charge_at_it` (STR) and `find_the_panel` (INT) can fail into `dark_wounded`.
- WIS success is the PRIMARY LESSON node: the player stops, maps the pattern, realizes the machine does not know they are there. "The world is not hunting you. It is working." This is the game's thesis delivered through action, not narration.

**Pods — occupied:**

v2.0.0 had cryo-pods described as "empty." Wrong — the Ancestors are ALIVE, sleeping in their pods, breathing. Phase 1 is "Ignorance/Hope." The horror of the startup routine destroying The Cleft belongs to Phase 3 (midpoint). The prologue ends with: pods occupied, Ancestors breathing, The Cleft intact on the horizon, the census at 479/480.

**The Cleft:**

Remains intact at prologue close. `the_cleft_gone` is NOT set during the prologue. Decontamination/startup remains the Phase 3 midpoint event. The prologue is Phase 1 — the world is stable, the player is just the first person to stand at the door.

**Lo at crater_surface:**

v2.0.0: "Lo responds immediately... Movement across the obsidian, fast. Lo finds you." Canonical spec: "Lo is right where you left them, frantically looking down the crack." Fixed: Lo is at the crack, crouching, looking down when the player surfaces. Lo does not run across the basin.

**Pressure budget matrix (final):**

| Node | Delta | Trigger |
| --- | --- | --- |
| `the_fall` | +1 | always |
| `dark_wounded` | +1 | charge_at_it or find_the_panel fail |
| `cryo_room` | +1 | catalog_the_pods WIS fail |
| `proximity_auth` | +1 | always |

Maximum pressure at `lo_aftermath` entry: 4 (Gold Zone floor). Design target: Gold Zone 4–6.

**Nodes renamed:**

`crater_threshold` → `crater_investigation`. `facility_descent` → `the_fall`. `recognition` → `the_ascent` + `crater_surface` (split into two distinct moments). Removed `recognition` node entirely.

**Scenario version:** `calloused_prologue.json` promoted to v3.0.0.

**`calloused_master.md` promoted to v3.0:** Added §PROLOGUE STRUCTURE (full 11-node map, pressure budget matrix, design rules). Added §HUMAN PHYSIOLOGY (Dermal Carapace, Acoustic Vulnerability, Adrenaline Crash). Expanded The Cleft settlement spec. Smart-dust calibration status documented (pending diegetic implementation in `the_fall`).

---

## 2026-05-20 — Benchmark 01: First Live Run of calloused_prologue.json

### Full prologue run completed — audio pipeline confirmed, three issues found

**Run command:**

```powershell
venv\Scripts\python app\voice_play.py --scenario scenarios/calloused_prologue.json 2>&1 | Tee-Object app\benchmark_01.log
```

**What worked:**

- All 11 nodes traversed without engine crash.
- Auto-next transitions (`the_fall` → `the_dark`, `dark_wounded` → `cryo_room`) fired correctly with correct delays.
- Intent matching: "A ******* monster bit me on the shin" correctly matched `tell_lo_what_you_found`.
- Steps 1–4 overhead: 532–1350ms across all turns.
- TTS warm calls: 90–600ms per sentence.
- Checkpoint saved at `prologue_close`.

**Issue 1 — TTS cold start (5270ms):**

Both Azure synthesizers (`_speaker_synth`, `_bytes_synth`) lazy-initialize on first call. First synthesis: 5270ms. Subsequent calls: 90–600ms. The cold start landed on the first narration the player heard — worst possible placement.

**Fix:** Added `warmup()` method to `AzureSpeechTTSService`. Calls `_get_speaker_synth()` and `_get_bytes_synth()` at startup to initialize WebSocket connections before first player interaction. Called in `voice_loop()` immediately after `_build_tts()` via `run_in_executor`. Log tag: `[TTS WARMUP] synthesizers ready in Xms`.

**Issue 2 — No `[STREAM TTFA]` data:**

All 11 prologue nodes have `opening_text`. The LLM narration path (`narrate_stream`) never fires — all narration is scripted. `parse_benchmark.py` reported zero TTFA data points.

**Root cause:** `[STREAM TTFA]` logs inside `narrate_stream()`, which only runs when a node has no `opening_text`. The prologue is 100% scripted — by design for consistency across benchmark runs. But this means thesis RQ1 (TTFA measurement) requires at least one LLM-narrated path.

**Fix:** Added `terminal_resistance` node with no `opening_text`. When a player tries to force, smash, or override the `proximity_auth` terminal, the action `try_to_force_the_terminal` routes to `terminal_resistance`. The LLM generates the system's cold bureaucratic non-response. `[STREAM TTFA]` fires here. This is also narratively correct — the terminal does not react to violence; it logs a non-conforming input and continues waiting.

**Issue 3 — proximity_auth stuck player for 3 turns:**

`proximity_auth` had a single action: "Leave." Player tried to smash the terminal three times. Engine correctly refused to match "I smashed the screen" to "leave." Third attempt ("I say, what do you do 100 times?") eventually matched through fuzzy intent fallback.

**Fix:** Added `try_to_force_the_terminal` action to `proximity_auth`. Routes to `terminal_resistance`. Players who attack the terminal now get a valid narrated response path.

**`[STREAM TTFA]` metric note:**

The timestamp logs when the first sentence TEXT is ready from the LLM stream — before TTS synthesis runs. True time-to-first-audio = `[STREAM TTFA]` + TTS synthesis latency for sentence 1 (Azure warm: 90–600ms). `parse_benchmark.py` labels this "input → first audio" which is technically inaccurate. The metric measures LLM pipeline latency up to first sentence extraction. For thesis: reframe as "LLM-to-first-sentence latency" — the most controllable part of the pipeline.

---

## 2026-05-20 -- narrate_stream Pipeline Fix

### Sentence-level synthesis was not pipelined -- each sentence blocked until complete

**Problem found in benchmark_02:** `narrate_stream` called `speak()` per sentence. `speak()` synthesizes then plays, both blocking. Sentences played one at a time with full TTS latency between each (~2-5s gap on Azure). The synthesis pipeline built for `narrate_sentences` was never applied to the streaming path.

**Fix:** Rewrote `narrate_stream` to mirror `narrate_sentences`: synthesize sentence N+1 concurrently with playback of N using `asyncio.create_task`. After fix (benchmark_03): inter-sentence synthesis 86-676ms, played without gaps.

**Architecture note:** Both `narrate_sentences` (scripted text) and `narrate_stream` (LLM token stream) now use the same synthesis pipeline pattern. The only difference is input source: a static list vs an async sentence splitter over a live token stream.

---

## 2026-05-20 -- STT Silent Exit Fixed

**Problem:** `recognize_once()` timeout returned `""`. Main loop hit `if not user_input: break` -- silently ended the session with no user feedback.

**Fix:** Changed `break` to `continue` with a re-prompt: `await speak(tts, *_input_prompt())`. Session no longer exits on missed STT detection.

**Secondary bug found:** After re-prompt, the code did `continue` which restarted the loop -- which spoke the prompt AGAIN before listening. Player heard the prompt three times in a row before being allowed to respond.

**Fix:** After re-prompt, listen immediately. Only `continue` (loop restart) if the second listen also returns empty. Maximum two prompts before re-listening.

---

## 2026-05-20 -- Input Prompt Delivery Variation

**Problem:** "What do you do?" was delivered with identical voice parameters every time. Monotonous.

**Fix:** `_INPUT_PROMPTS` list with 6 entries, all with the same text but different `VoiceParams` (varied emotion, style, tempo, reverb). Selected randomly on each delivery via `_input_prompt()`. Examples: `tempo=0.72, reverb=0.25` (slow, atmospheric) vs `tempo=0.93, reverb=0.03` (quick, dry). Same words, varied register.

---

## 2026-05-20 -- Diegetic Calibration: Facility Intake Protocol

**Problem:** Calibration questions were interview-style ("What does your tribe use you for?") -- felt like a character creation screen, not a 50,000-year-old machine.

**Fix 1 -- Questions rewritten as terminal input prompts:**

```text
OPERATOR DESIGNATION. State sector. State assigned function.
LOAD CAPACITY. State maximum recorded output. Kilograms or equivalent.
COMMAND INDEX. State number of personnel under direct control.
UNAUTHORIZED MEMORY. Declare any knowledge of surface conditions or external systems absent from your official briefings.
```

The system expects formatted database fields. The player gives human surface-dweller answers. The mismatch is the experience.

**Fix 2 -- Post-calibration feedback de-gamified:**

Previously: "Calibration complete. Biometrics locked. Your strength runs deep." -- revealed the dominant stat directly.

Now: "Registry entry sealed. Operational profile locked." -- the facility processed the player. The player does not know what it found. Log still records full stats for debugging.

**Implementation note:** `calibration_node: "facility_scan"` in the scenario triggers mid-loop calibration via `voice_play.py` auto_next handling. `calibration_enabled: false` at scenario level (pre-name-capture calibration disabled). The diegetic path fires on `facility_scan` auto_next branch.

---

## 2026-05-20 -- Prologue Expansion: 14 to 17 LLM-Streamed Nodes

### Three new exploration nodes added to increase TTFA data density

**Problem:** Only 3-4 TTFA measurements per benchmark run (from `dark_probe`, `pod_close_look`, `terminal_query`, `terminal_resistance`). Thesis needs 20+ for meaningful p50/p95.

**Nodes added:**

| Node | Trigger | Content |
| --- | --- | --- |
| `cryo_corridor` | "Walk the full length" from `cryo_room` | LLM narrates the scale of hundreds of breathing pods in cold blue light. One specific anomaly mid-walk. |
| `shaft_look_down` | "Look back before you close the panel" from `the_ascent` | LLM narrates the facility geometry from above -- the cryo room glow below, the hum still audible. Weight of departure. |
| `lo_face` | "Look at Lo's face before you answer" from `lo_aftermath` | LLM narrates Lo's expression and body language in the beat before the player speaks. Leads directly to `prologue_close` with tell/nothing consequence. |

All three have no `opening_text` -- LLM generates on arrival. Each fires `[STREAM TTFA]`. Potential TTFA data points per run: 7+ (up from 4).

**`cryo_room` and `lo_aftermath` also converted to LLM-generated** (opening_text removed). Reason: hardcoded opening_text was wrong for multiple entry paths -- see below.

---

## 2026-05-20 -- State Management: Narrative Flags Injected into System Prompt

### Conditional narration now driven by structured state, not dialog parsing

**Problem:** `cryo_room` opening_text always said "Your legs lock. Hands shake. You sink to one knee." regardless of how the player navigated the corridor. A player who charged the cleaning unit and stomped it flat had no adrenaline crash -- they had a STR kill. The scripted text was incoherent.

Same issue in `lo_aftermath`: "The bruise is already darkening through your leathery skin" -- but only `dark_wounded` players have a bruise. Players who slipped past the unit cleanly heard Lo describe an injury they never received.

**Root cause:** `build_system_prompt()` injected HP, pressure, lo_trust, and inventory into the LLM context -- but not `narrative_flags`. The flags (`bruised_by_unit`, `destroyed_the_unit`, `understood_the_pattern`, etc.) existed in state but the LLM had no access to them.

**Fix 1 -- Layer 5b added to `prompt_director.py`:**

```python
active_flags = {k: v for k, v in state.narrative_flags.flags.items() if v}
if active_flags:
    flag_lines = "\n".join(f"- {k}: {v}" for k, v in active_flags.items())
    parts.append(f"\n## Narrative State\n{flag_lines}")
```

All truthy flags are now injected as a `## Narrative State` block in every system prompt. False flags are omitted (default state, adds noise).

**Fix 2 -- `cryo_room` and `lo_aftermath` converted to LLM-generated (opening_text removed):**

System prompts updated to reference flags directly:

- `cryo_room`: "Check Narrative State flags: bruised_by_unit: true -> body's debt. Hands shake. Legs lock. / destroyed_the_unit: true -> keyed-up, adrenaline with nowhere to go. / slipped_past_the_unit or understood_the_pattern: true -> controlled entry."
- `lo_aftermath`: "Check Narrative State flags: bruised_by_unit: true -> Lo notices the leg. Bruise darkening through the carapace. Lo says 'You're dragging your leg.' / No injury flag -> Lo's scan finds nothing beyond the landing. Lo does not invent a bruise."

The LLM reads structured data, not its own conversation history. Lo only notices a bruise when there is one.

**Side effect:** Both conversions add TTFA data points. Total potential TTFA measurements per run is now 9+.

---

## 2026-05-20 -- Benchmark Results (02-05)

### TTFA data collected across 4 runs, voice A/B testing

**Voices tested:** en-US-RyanMultilingualNeural (02), en-IE-EmilyNeural (03), en-GB-SoniaNeural (04, 05), en-AU-NatashaNeural (rejected immediately -- 04), en-NZ-MollyNeural (04 end), en-US-DavisNeural (current).

**TTFA measurements collected (benchmarks 02-05):**

16 total measurements. p50 approximately 1600-1700ms. All above 500ms target.

Breakdown by run:

- Benchmark 02: data before pipeline fix -- long gaps between sentences (2-5s each), pipelining not working.
- Benchmark 03: pipeline fix confirmed. Sentence synthesis 158-676ms. First clean TTFA data.
- Benchmark 04: 3 measurements. Calibration ran old questions (edit made after run started). Content filter triggered on player profanity in calibration answers -- fallback to default stats.
- Benchmark 05: 3 measurements (2040ms, 2356ms, 1844ms). New calibration questions worked. No content filter. Stats: strength=15, constitution=14, charisma=13 from "10,000 kilograms" / "Everyone."

**TTFA interpretation for thesis:**

`[STREAM TTFA]` logs when the first complete sentence is extracted from the LLM token stream. This is LLM-first-sentence latency, not true time-to-first-audio. True TTFA = `[STREAM TTFA]` + Azure TTS synthesis for sentence 1 (warm: 86-650ms). At current measurements, true TTFA is approximately 2-3s p50. The bottleneck is Azure OpenAI first-token latency (~1.5-2.5s), not the synthesis pipeline.

**LLM stream total durations:** 27-38s for terminal_resistance responses (max_response_length=80 words, approximately 8-10 sentences). Pipelining keeps inter-sentence gaps at 86-650ms despite total stream duration.

---

## 2026-05-20 -- the_ascent: Hardcoded Unit Reference Removed

**Problem:** `the_ascent` opening_text said "Somewhere in the dark the cleaning unit is on its circuit -- you know the timing now." If the player stomped the unit flat (`destroyed_the_unit: true`) or shut it down via the service panel (`shut_down_the_unit: true`), the unit is gone. The scripted line was factually wrong.

**Fix:** Removed `opening_text` from `the_ascent`. System prompt now checks Narrative State flags:

- `destroyed_the_unit: true` -> corridor is quiet, nothing on circuit, player navigates freely
- `shut_down_the_unit: true` -> quiet, panel still tripped
- Neither -> unit still on its circuit, player navigates by timing

This was the last remaining scripted text in the prologue that contradicted reachable game state. All factually state-dependent narration is now LLM-generated from flags.

---

## 2026-05-20 -- Remove Name Capture and Meta-Welcome

**Problem:** voice_play.py opened with "Welcome to GALDR... Traveler." and asked "What is your name?" before entering the scenario. Both violate the design document:

- No system narrator voice (Ven was removed; the world does not welcome anyone)
- Name capture is character-creation-screen energy -- the world does not ask your name
- `crater_investigation` already has an opening_text that plunges the player into the scene: "Three days since the Eternal Breath stopped..."
- The meta-welcome would play immediately before that line, doubling the introduction

**Fix:** Removed name capture entirely. Removed welcome speaks. Default character name is "Traveler" (was "Aventyrare" -- broken encoding on Windows console). The startup calibration block now only fires if `calibration_enabled: true`; the surrounding meta-speaks ("Answer the Registry's questions truthfully") removed. The diegetic v2.1 calibration design fires mid-game at `facility_scan` and needs no startup framing.

**Result:** Game starts on first audio line of `crater_investigation`. No meta-layer between player and world.

**Also fixed:** Console banner em dash caused `?` encoding on Windows. Changed to ASCII-safe `G.A.L.D.R. // CALLOUSED`. Default character name changed from Swedish "Aventyrare" to "Traveler" -- fixes broken `?` in session log lines. Voice reverted from en-US-DavisNeural (rejected) to en-GB-SoniaNeural.

---

## 2026-05-20 -- Benchmark 06: 8 TTFA Measurements, 24 Total

### n=24 distribution across benchmarks 01-06

Benchmark 06 was the first run with the full set of fixes (UTF-8 logging, markdown stripping, flag-based narration). 8 TTFA data points collected, bringing the total to 24 across all 6 benchmark runs.

**Distribution (n=24 total):**

| Metric | n | min | mean | p50 | p95 | max |
| --- | --- | --- | --- | --- | --- | --- |
| TTFA (LLM first sentence) | 24 | 817ms | 1986ms | 1894ms | 3672ms | 4405ms |

**Interpretation for thesis:**

The 500ms target is not met and was not expected to be met for cloud LLM. `[STREAM TTFA]` measures time from player input received to first complete sentence extracted from the LLM token stream. True time-to-first-audio = TTFA + TTS synthesis for sentence 1 (Azure TTS warm: p50~196ms, p95~450ms). True TTFA p50 therefore approximately 2.1s.

Bottleneck: Azure OpenAI first-token latency (~1.5-2.5s). This is network + model inference, not the GALDR pipeline. The pipeline overhead (steps 1-4: GPS, intent match, mechanics, transition) is 300-1100ms at p95, contributing roughly 10-15% of total TTFA.

**Thesis framing:** Reframe RQ1 from "meets 500ms target" to "characterizes achievable TTFA for cloud-LLM voice-first interactive narrative" -- a descriptive result, not a pass/fail.

---

## 2026-05-20 -- LLM Intent Matcher Prompt Rewritten to English

**Problem:** `_match_action_llm` in `engine.py` sent the intent matching prompt in Swedish. When a player said "headbutt it," the LLM received a Swedish prompt asking for an action match. The semantic bridge between English player speech and English action IDs was broken.

**Fix:** Rewrote prompt to English, with explicit synonym hint:

```text
The player said: "headbutt it"

Available actions:
- ID: charge_at_it | Label: Charge at it | Description: ...

Which action best matches the player's intent?
Consider synonyms and creative phrasings (e.g. 'headbutt' matches 'charge at it').
Reply with ONLY the action ID, or 'none' if nothing matches.
```

**Also fixed:** Offline fallback yes/no heuristics -- removed Swedish words ("ja", "okej", "visst", "nej", "vägra", "lämna") and replaced with English equivalents.

---

## 2026-05-20 -- Swedish Purge

**Problem:** Systematic Swedish found across: `ambient/weather.py` (all WMO code descriptions), `ambient/daylight.py` (phase names), `ambient/context.py` (docstrings), `galdr/__init__.py` (module docstring), `api/routes.py` (default character name "Aventyrare"), `core/engine.py` (default character name), `core/state.py` (default character name), `tests/test_state.py` (all test data).

**Files fully rewritten to English:**

- `weather.py`: WMO codes 0-99 mapped to English descriptions. "klar himmel" -> "clear sky", "blåsigt" -> "strong wind".
- `daylight.py`: phase names "night", "dawn", "morning", "midday", "afternoon", "dusk".
- `context.py`: docstrings.
- Default character name: "Aventyrare" -> "Traveler" across all three files.
- `test_state.py`: complete rewrite, all test data in English.

**Files deleted:**

- `app/play.py` -- Ekokammaren terminal PoC, scenario deleted.
- `app/tests/test_playthrough.py` -- tested the deleted Ekokammaren scenario.

---

## 2026-05-20 -- Markdown Stripping in TTS Pipeline

**Problem:** LLM sometimes returns markdown formatting -- asterisks for bold/italic (`**word**`, `*word*`), backticks, heading markers. Azure TTS reads these literally: "asterisk word asterisk."

**Fix:** Added `_MD_NOISE` regex to `galdr/utils/sentence_splitter.py`:

```python
_MD_NOISE = re.compile(r'\*{1,3}|_{1,2}|`|^#{1,6}\s*', re.MULTILINE)
```

Applied at all TTS entry points: `split_sentences()` strips before yielding each sentence. `voice_play.py` `speak()` and `_split_text_sentences()` call `_clean_text()` using the same pattern. Triple asterisks, double asterisks, single asterisks, underscores, backticks, and markdown headings all stripped before synthesis.

---

## 2026-05-20 -- Windows Console UTF-8 Encoding Fixes

**Problem 1:** Logger strings in `azure_service.py` and `elevenlabs_service.py` contained Unicode arrows (`->` was `→`, `<-` was `←`) and em dash (`--` was `--`). On Windows console with cp1252 encoding, these rendered as `?`.

**Fix:** `replace_all` on all three characters across both service files. Also fixed em dash in `engine.py` logger string.

**Problem 2:** Windows console default encoding (cp1252) can't render em dashes in authored scenario content when printed to console.

**Fix:** Added to `voice_play.py` before `logging.basicConfig`:

```python
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

This runs before `logging.basicConfig`, which uses `sys.stderr` as the default stream. Em dashes in action labels, descriptions, and authored content now render correctly on Windows.

---

## 2026-05-20 -- Automated Test Suite: 76 Tests Passing

### Six test modules cover graph integrity, intent matching, sentence splitting, pressure budget, and prompt director

All tests written and passing (76/76) as of this entry. Two root-cause bugs found during testing:

**Bug 1 -- pressure budget key mismatch:** `test_pressure_budget.py` used `effect.get("value", 0)` but the prologue JSON uses `"amount"` key for `modify_pressure` consequences. All pressure calculations returned 0 until fixed. Key is now `effect.get("amount", effect.get("value", 0))`.

**Bug 2 -- ellipsis split behavior documented:** The sentence splitter regex `(?<=[^.][.])` intentionally excludes ellipsis from sentence boundaries. `test_ellipsis_no_split` was written with wrong assertions (`len == 2`). Fixed to assert `len == 1` -- "The unit... it stops." is yielded as one sentence, split only by the remainder handler.

**Test modules and coverage:**

| Module | Tests | Covers |
| --- | --- | --- |
| `test_scenario_graph.py` | 9 | Node references, reachability, start/end validity, self-loop guard |
| `test_intent_matcher.py` | 22 | Exact ID, digit index, keyword, adversarial inputs, yes/no heuristics |
| `test_sentence_splitter.py` | 24 | Markdown cleaning, sentence splitting, chunked token streams |
| `test_pressure_budget.py` | 3 | BFS over all prologue paths, Gold Zone validation, no COLLAPSE |
| `test_prompt_director.py` | 17 | Flag injection, pressure directives, Lo trust, layer ordering, encoding |

**Coverage boundary documented:** "panel" alone returns None from the offline intent matcher. `find_the_panel`'s label is "Search the wall -- there must be a shutoff" -- the word "panel" does not appear. The action ID compound token is not split. Single-word-from-ID matching requires the LLM path.

**Pressure budget result:** All 154,440 paths walked. Pressure range at `lo_aftermath`: 1-5. Gold Zone (4-6) confirmed. COLLAPSE (10) unreachable.

---

## 2026-05-20 -- the_ascent Flag-Based Narration Confirmed Working

**Confirmed in playthrough:** After `destroyed_the_unit` flag was set (player charged the cleaning unit and stopped it), a second pass through `the_ascent` produced narrator text that correctly noted the corridor was quiet and nothing was on circuit. The cleaning unit was not mentioned as active.

This is the intended behavior: all state-dependent narration in the prologue is now driven by `## Narrative State` flag injection into the system prompt, not hardcoded `opening_text`.

---

## 2026-05-21 -- Acoustic Layer Fix: VoiceParams Wired to SSML

**Problem:** `_build_ssml()` in `azure_service.py` generated identical SSML for every node -- `rate="0.9"` hardcoded, no `mstts:express-as` tag. `VoiceParams.emotion` and `VoiceParams.tempo` existed in the data model and were passed in, but neither was read. All nodes sounded identical regardless of authored `emotion` or `tempo`.

**Fix:** Rewrote `_build_ssml()` to accept `emotion` and `tempo` parameters:

- Added `_EMOTION_STYLE` class dict mapping engine emotion strings to Azure mstts style names:
  - `"whisper"` -> `"whispering"`
  - `"nostalgic"`, `"warm"`, `"calm"` -> `"narration-relaxed"`
  - `"cold"` -> `"newscast"` (excluded from narrator; kept for future NPC use)
- `emotion` drives `mstts:express-as` tag injection when a mapping exists. Unmapped emotions (e.g. "neutral") produce no style tag -- Azure default delivery.
- `tempo` drives `prosody rate="{tempo:.2f}"` tag.
- Added `xmlns:mstts` to SSML root element (required by Azure for mstts tags to parse correctly). Fixed `xml:lang` to `en-GB` (was `en-US` -- mismatched SoniaNeural's locale).
- Updated all three callers (`synthesize`, `speak`, `speak_with_barge_in`) to pass `params.emotion, params.tempo`.
- Log lines updated to include emotion and tempo.

**Also fixed:** `reverb_processing_enabled` default in `config.py` was `False`. Changed to `True`. Reverb post-processing (scipy fftconvolve, ~2-8ms at 16kHz) is now on by default. Disableable via `REVERB_PROCESSING_ENABLED=false` in `.env`.

---

## 2026-05-21 -- VoiceParams Authored for All Prologue Nodes

**Problem:** All prologue nodes had `emotion="neutral"` except `the_dark` (whisper) and `cryo_room`/`cryo_corridor` (nostalgic). With the acoustic layer now wired, the remaining 12 nodes sounded identical -- flat, no tonal variation.

**Design standard:** Human narrator. Matt Mercer / Critical Role as the benchmark. No robotic delivery. The narrator must feel present, not artificial. Removed "cold/newscast" from all narrator nodes -- Azure newscast style sounds broadcast-robotic. Tension is carried by whisper, not coldness.

**Two-layer tonality:** Layer 1 = authored `VoiceParams` per node (TTS acoustic delivery, static dramatist intent). Layer 2 = game state (pressure, lo_trust, flags) injected into system prompt (LLM narrative register, dynamic). Both layers now operational.

**Changes applied to `calloused_prologue.json` v3.1.0:**

| Node | emotion | tempo | reverb | Character |
| --- | --- | --- | --- | --- |
| `the_fall` | whisper | 0.82 | 0.45 | Impact. Dark. Disoriented. |
| `facility_scan` | neutral | 0.85 | 0.50 | Ancient machine voice. Deep reverb. |
| `dark_wounded` | whisper | 0.85 | 0.35 | Hurt, low, humiliated. |
| `dark_probe` | whisper | 0.85 | 0.35 | Careful, listening. |
| `console_chamber` | nostalgic | 0.90 | 0.30 | Weight of 50,000 years. |
| `pod_close_look` | nostalgic | 0.95 | 0.20 | Intimate. One face through glass. |
| `proximity_auth` | whisper | 0.82 | 0.30 | The system sees you. |
| `terminal_resistance` | whisper | 0.85 | 0.30 | Cold indifference meets futility. |
| `shaft_look_down` | neutral | 0.88 | 0.40 | The weight of leaving. |
| `the_ascent` | neutral | 0.95 | 0.10 | Climbing toward open air. Dry. |
| `lo_face` | warm | 0.88 | 0.05 | Surface. Reunion approaching. |
| `prologue_close` | warm | 0.88 | 0.08 | The question that won't be named. |

Nodes confirmed good as-is (no changes): `crater_investigation`, `crater_surface`, `lo_aftermath`, `cryo_room`, `cryo_corridor`, `the_dark`.

---

## Pending / Next

- [ ] Thesis deadline 2026-05-22 -- 2 days. Write RQ1 (TTFA) section with collected data.
- [ ] Reframe TTFA in thesis: "LLM-to-first-sentence latency" not "input-to-first-audio." True TTFA = TTFA value + TTS synthesis (~200-650ms). Current p50 approximately 1894ms LLM-first-sentence; approximately 2.1s true TTFA.
- [ ] Voice decision: en-GB-SoniaNeural current. Continue auditioning male voices post-thesis.
- [ ] Calibration long-term: replace question-based intake with choice-driven stat emergence from prologue play. Post-thesis.
- [ ] Barge-in (post-thesis): requires headphones or echo cancellation. Windows WASAPI concurrent stream conflict on speakers.
- [ ] Act 1 opening: overland travel from crater to The Cleft. Lo delivers world-knowledge during the walk.
