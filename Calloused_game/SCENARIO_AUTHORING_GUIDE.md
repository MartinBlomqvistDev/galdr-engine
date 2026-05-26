# GALDR Engine — Scenario Authoring Guide

**For external collaborators and AI assistants.**
This document is self-contained. You do not need any other project context to write or extend a GALDR scenario.

---

## What This Is

A GALDR scenario is a **directed graph of nodes** stored as a single JSON file in `app/scenarios/`. Each node is a scene. The player moves through the graph by taking actions. The AI narrator generates dialogue within each scene, but the graph topology (what exists, what leads where) is fixed by the author.

**The author controls:** what exists, what the player can do, where choices lead, when state mutates.
**The AI controls:** how narration sounds — word choice, texture, emotion.

Scenarios are loaded by Python class `Scenario` (Pydantic v2). Every field name below matches the Python model exactly. Unknown fields are ignored; required fields that are missing will cause a load error.

---

## Scenario Top Level

```json
{
  "id": "my_scenario",
  "title": "Human-readable title",
  "description": "One sentence about what this scenario is.",
  "author": "Your name",
  "version": "1.0.0",
  "global_system_prompt": "Applied as base system prompt to every node. Set the narrator's overall tone here.",
  "start_node": "arrival",
  "end_nodes": ["ending_a", "ending_b"],
  "calibration_enabled": false,
  "default_voice": { "character_name": "Narrator", "emotion": "neutral", "reverb": 0.1, "style": "narrator" },
  "nodes": { ... }
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | string | yes | Snake_case, unique across all scenarios |
| `title` | string | yes | |
| `description` | string | yes | |
| `author` | string | no | |
| `version` | string | no | Default `"1.0"` |
| `global_system_prompt` | string | no | Prepended to every node's `system_prompt` |
| `start_node` | string | yes | Must match a key in `nodes` |
| `end_nodes` | array of strings | yes | At least one. These nodes end the session. |
| `calibration_enabled` | bool | no | Default `false`. If `true`, runs the 4-question Tribal Service stat calibration before the opening node. CALLOUSED has this disabled since v3.2.0 (diegetic stat emergence replaced it). |
| `default_voice` | VoiceParams | no | Used when a node has no `voice` field |
| `nodes` | object | yes | Keys are node IDs; values are NarrativeNode objects |

---

## NarrativeNode

Each value in `nodes` is a node object:

```json
"some_node": {
  "id": "some_node",
  "title": "Short scene title",
  "description": "Internal note — never read aloud. Dramaturg's reminder of what this scene is for.",
  "system_prompt": "Instructions to the AI for this scene. Mood, focus, what to emphasize.",
  "opening_text": "Fixed prose read aloud on entry. Verbatim. The AI does not generate this.",
  "voice": { "character_name": "Narrator", "emotion": "neutral", "reverb": 0.1, "style": "narrator" },
  "is_checkpoint": false,
  "forbidden_topics": [],
  "max_response_length": 80,
  "actions": [ ... ],
  "on_enter": [ ... ]
}
```

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | string | required | Must match the key in `nodes` |
| `title` | string | required | |
| `description` | string | required | Internal note only |
| `system_prompt` | string | `""` | AI direction for this scene. Good practice: tell the AI what tone, what to focus on, what not to reveal yet. |
| `opening_text` | string | `""` | Fixed text narrated verbatim on node entry. **Use for key beats, discoveries, and endings.** If empty, the AI generates the opening. |
| `context_hint` | string | `""` | Extra mood/genre hint injected after `system_prompt` |
| `voice` | VoiceParams | default_voice | Per-node voice/acoustic settings (see §VoiceParams) |
| `is_checkpoint` | bool | `false` | If `true`, engine saves game state when this node is entered. Narrator says: *"Biometrics stabilizing. Neural backup synchronized."* |
| `forbidden_topics` | array of strings | `[]` | e.g. `["violence", "sex"]`. AI guardrail. |
| `max_response_length` | int | `300` | Max words in AI-generated response. Keep to 60–100 for voice-first play. |
| `actions` | array of NodeAction | `[]` | What the player can do. Empty = end node or auto-transition. |
| `on_enter` | array of Consequence | `[]` | State mutations applied automatically when the node is entered, before actions. |
| `entry_conditions` | array of Condition | `[]` | Node is locked unless all conditions pass. Rarely needed — prefer gating via action conditions. |
| `auto_next` | string or null | `null` | Node ID to transition to automatically without player input. Use sparingly. |
| `auto_delay_seconds` | float | `0.0` | Seconds to wait before `auto_next` triggers. |

### End nodes

End nodes are listed in `end_nodes` and must have **no actions** (or the game loop will not exit). They should have both `opening_text` (the closing line) and `system_prompt` (in case the AI generates a farewell). The engine stops accepting input once an end node is reached.

---

## NodeAction

```json
{
  "id": "read_the_letter",
  "label": "Read the letter",
  "description": "The player opens the envelope and reads the handwritten letter inside.",
  "target_node": "letter_contents",
  "skill_check": null,
  "dc": 10,
  "failure_node": "",
  "conditions": [],
  "consequences": [],
  "failure_consequences": []
}
```

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | string | required | Snake_case, unique within the node |
| `label` | string | required | Short player-facing text. Read aloud as a choice prompt. |
| `description` | string | `""` | Stage direction fed to the AI. Describes what the player does. Not read aloud. |
| `target_node` | string | `""` | Node to transition to on success (or when no skill check). |
| `skill_check` | string or null | `null` | Ability name if this action requires a roll. See §Ability Names. |
| `dc` | int | `10` | Difficulty class (8=easy, 10=standard, 12=moderate, 14=hard, 16=very hard, 18=extreme). |
| `failure_node` | string | `""` | Node to transition to on failed skill check. If empty and check fails, player stays in current node. |
| `conditions` | array of Condition | `[]` | All must pass for this action to appear. |
| `consequences` | array of Consequence | `[]` | Applied on success. |
| `failure_consequences` | array of Consequence | `[]` | Applied on failure. |

---

## Ability Names

Used in `skill_check` fields and `stat` conditions.

| String | Stat | Narrative Use |
| --- | --- | --- |
| `"strength"` | STR | Forcing, lifting, breaking |
| `"dexterity"` | DEX | Speed, stealth, fine motor |
| `"constitution"` | CON | Endurance, poison, environmental stress |
| `"intelligence"` | INT | Deduction, recall, decoding, technical |
| `"wisdom"` | WIS | Perception, intuition, reading people |
| `"charisma"` | CHA | Persuasion, intimidation, performance |

In CALLOUSED, the narrator describes outcomes qualitatively — never reads a number aloud. A 15 STR player who fails a DC 14 check: "You throw your whole weight against it. It holds." A success at DC 14: "The hinge buckles with a sound like a gunshot."

---

## Conditions

Used in `conditions` (action visibility) and `entry_conditions` (node access). All conditions in a list must pass (AND logic).

```json
{ "type": "flag",    "key": "met_elder",    "value": true }
{ "type": "stat",    "ability": "strength", "min": 14 }
{ "type": "item",    "item_name": "Filter-Mask" }
{ "type": "visited", "location": "the_cleft" }
{ "type": "turn",    "min": 3 }
{ "type": "always" }
```

| `type` | Required fields | Notes |
| --- | --- | --- |
| `flag` | `key`, `value` | True if `narrative_flags[key] == value` |
| `stat` | `ability`, optionally `min` and/or `max` | True if ability score is within range |
| `item` | `item_name` | True if player has this item in inventory |
| `visited` | `location` | True if location was visited this session |
| `turn` | `min` | True if turn count >= min |
| `always` | — | Always true. Useful as a default condition. |

---

## Consequences

Applied via `consequences`, `failure_consequences`, or `on_enter`.

```json
{ "type": "set_flag",    "key": "door_open",  "value": true }
{ "type": "add_item",    "item_name": "Thermal Glass Blade", "item_description": "A blade forged at The Vent." }
{ "type": "remove_item", "item_name": "Thermal Glass Blade" }
{ "type": "modify_hp",   "amount": -6 }
{ "type": "set_weather", "value": "acid rain" }
{ "type": "set_time",    "value": "nightfall" }
{ "type": "visit_location", "location": "vestal", "location_name": "Vestal" }
```

| `type` | Required fields | Notes |
| --- | --- | --- |
| `set_flag` | `key`, `value` | Sets a named narrative flag. Value can be bool, string, or int. |
| `add_item` | `item_name`, optionally `item_description` | Adds item to inventory |
| `remove_item` | `item_name` | Removes first matching item |
| `modify_hp` | `amount` | Positive = heal, negative = damage. Clamped to 0–max_hp. |
| `set_weather` | `value` | String describing current weather |
| `set_time` | `value` | String describing time of day |
| `visit_location` | `location`, optionally `location_name` | Marks a location as visited |

---

## VoiceParams

```json
{
  "character_name": "Narrator",
  "emotion": "neutral",
  "reverb": 0.1,
  "pitch_shift": 0.0,
  "tempo": 1.0,
  "style": "narrator"
}
```

| Field | Type | Default | Allowed values |
| --- | --- | --- | --- |
| `character_name` | string | `"Narrator"` | Any string. Used internally; not read aloud. |
| `emotion` | string | `"neutral"` | `neutral`, `warm`, `whisper`, `nostalgic`, `threatening`, `cold` |
| `reverb` | float | `0.0` | `0.0` (dry) to `1.0` (heavy echo). Suggested: 0.05 outdoors, 0.1 indoor, 0.2 stone corridor, 0.3 cavern. Applied as scipy fftconvolve post-processing on raw PCM. |
| `pitch_shift` | float | `0.0` | `-1.0` (very deep) to `1.0` (very high). Not implemented in current Azure backend; reserved. |
| `tempo` | float | `1.0` | `0.5` (slow) to `2.0` (fast). Applied to Azure SSML prosody rate. |
| `style` | string | `"narrator"` | `narrator`, `character`, `whisper`, `dramatic` |

**Emotion guide for CALLOUSED:**
- `neutral` — standard narration, glass crater, neutral information
- `warm` — emotional weight, warmth, relief, endings with hope
- `threatening` — danger, tension, aftermath
- `whisper` — stealth sections, tight spaces, the Underground
- `nostalgic` — ruins, Worker Logs, relics, memories of the surface world
- `cold` — the Ancestors speaking (even second-hand through logs)

---

## Narrative Writing Rules

### Voice
- **Always second-person.** "You smell smoke." Never "the character smells smoke."
- **No gendered pronouns for the player.** Gender-neutral by default.
- **Present tense preferred** for `opening_text`. "The staircase groans" not "The staircase groaned."
- **Short and concrete.** Voice-only means no re-reading. One sentence = one idea.

### Word limits
- `opening_text`: aim for 40–80 words. Enough to set scene; short enough to hold in working memory while listening.
- `system_prompt`: 50–120 words. Direct instructions to the AI. No prose; imperative sentences.
- `max_response_length`: set to 60–100 for voice-first play. Players cannot skim audio.

### What to author vs. what to leave to the AI
- **Author** (`opening_text`): scene-setting on entry, key discoveries, endings, checkpoint beats, any line where the exact words matter.
- **Leave to AI** (`system_prompt`): responses to player input, elaboration on authored setup, moment-to-moment narration during action.
- **Never put a key story reveal in a `system_prompt` alone.** The AI may de-emphasize it. Use `opening_text` for reveals.

### Description style
- Sensory and physical. Sound over sight — the player has no screen.
- "The floor is ice-smooth obsidian under your boots" not "the room looks like it's made of black glass."
- Hazards are discovered through sensation first: heat, smell, sound.

---

## CALLOUSED — World & Story Conventions

### Setting quick reference

| Location | Atmosphere | Key sensory detail |
| --- | --- | --- |
| Glass Crater | Hot, silent, disorienting | Obsidian underfoot, thermal shimmer, no wind |
| The Choke | Suffocating, verdant, loud | Stone-bark groaning, 35% O2 feels thick, Slag-Crawler sounds |
| The White Sea | Blinding, vast, eerie | Salt crunch, sinkholes, metallic tang |
| The Singing Ruins | Maddening, beautiful | Wind through whistle-holes, ceramic dust, distant pipe-organ tone |
| The Underground | Sterile, still, 20°C | No smell, no wind, footsteps echo perfectly, anxiety of perfection |
| The Cleft | Home, vertical, cramped | Rope bridges, goat smell, distant hammering |
| Vestal | Commerce, neutral, ancient | Fossilized bone arch above, trade voices, grease smell |
| The Vent | Industrial, intense heat | Forging sounds, thermal glass gleam, sweat |

### The player character
- Short, dense, calloused skin, broad heavy hands. Built for endurance, not speed.
- Strengths: strength, constitution. Weakness: fine dexterity, digestion of "pure" foods, sudden loud noises.
- Default name captured at session start by voice prompt. Always use their name when the narrator addresses them directly.

### Lo
- Lean tracker, gender-neutral, thermal-glass spear.
- Lo is never voiced — narrator-only.
- If `lo_dead` flag is `true`, the narrator stops mentioning Lo. No announcement. Absence does the work.
- Never write a node that announces "you are alone" as a direct statement when Lo is gone.

### Stat calibration (Tribal Service)
Only active when `"calibration_enabled": true`. The engine asks 4 questions before the opening node; an LLM assigns the D&D standard array `{15, 14, 13, 12, 10, 8}` across the six stats. The narrator then confirms the dominant stat: "Calibration complete. Your strength runs deep." — or wisdom, dexterity, etc.

### Forbidden content (all scenarios)
- Sexual content
- Real-world religion, politics, specific living individuals
- Breaking fourth wall (no "as an AI...", no out-of-character commentary)

### Numbers stay hidden
The narrator **never reads a stat value or roll result aloud**. Outcomes are always qualitative:
- Spectacular success (rolled 10+ over DC): dramatic, evocative language
- Success (beat DC by 1–4): clean, efficient narration
- Failure (missed DC): consequence lands, no apology
- Catastrophic failure (missed DC by 5+): pain, disorientation, flagging

---

## Full Example Node

```json
"dark_corridor": {
  "id": "dark_corridor",
  "title": "The Dark Corridor",
  "description": "Player enters a facility corridor with no light. Must navigate by sound or find a light source. A maintenance unit is on circuit nearby.",
  "system_prompt": "The player is in total darkness inside an ancient facility corridor. The air smells of ceramics and dry machine oil. Something moves — a low rhythmic sound, close. The player cannot see. Build unease slowly. The unit does not know the player is here. It is working.",
  "opening_text": "The passage seals behind you and the darkness is total. No light anywhere. The air is dry, ceramic-clean, and still. But something moves — a low rhythmic sound, coming from ahead, maybe three meters. The floor is smooth under your boots.",
  "voice": {
    "character_name": "Narrator",
    "emotion": "whisper",
    "reverb": 0.2,
    "style": "narrator"
  },
  "is_checkpoint": false,
  "forbidden_topics": ["sex", "religion"],
  "max_response_length": 70,
  "on_enter": [
    { "type": "set_flag", "key": "in_corridor", "value": true }
  ],
  "actions": [
    {
      "id": "move_toward_sound",
      "label": "Move carefully toward the sound",
      "description": "Player moves slowly forward, arms out, listening to locate the source.",
      "skill_check": "dexterity",
      "dc": 14,
      "target_node": "corridor_past_unit",
      "failure_node": "corridor_injured",
      "consequences": [],
      "failure_consequences": [
        { "type": "set_flag", "key": "shin_bruised", "value": true }
      ]
    },
    {
      "id": "wait_and_listen",
      "label": "Stay still and listen",
      "description": "Player goes motionless, mapping the room by sound alone.",
      "skill_check": "wisdom",
      "dc": 10,
      "target_node": "corridor_surveyed",
      "failure_node": "dark_corridor",
      "consequences": [
        { "type": "set_flag", "key": "corridor_mapped_by_sound", "value": true }
      ],
      "failure_consequences": []
    },
    {
      "id": "feel_for_wall",
      "label": "Feel along the wall for anything useful",
      "description": "Player backs to the nearest wall and sweeps it with both hands, looking for a switch or panel.",
      "target_node": "corridor_found_panel",
      "conditions": [
        { "type": "flag", "key": "in_corridor", "value": true }
      ],
      "consequences": [
        { "type": "add_item", "item_name": "Data Card", "item_description": "A ceramic wafer. Surface markings in a script you cannot read." }
      ]
    }
  ]
}
```

---

## Latency — What Authors Control

The engine uses a sentence-level streaming pipeline. TTFA (time to first audio after player input) is approximately:

> Pre-LLM pipeline (~180ms) + Azure first-token latency (~1.6s) + TTS synthesis warm (~200-650ms) ≈ **~2-2.5s** to first audio. Source: benchmark 08, Azure gpt-4o, en-GB-RyanNeural.

Authors can reduce TTFA by:

- **Writing short opening sentences in `system_prompt`.** The first sentence the LLM generates is what determines TTFA. Prompts that front-load a short punchy sentence ("The blade finds you.") reduce TTFA vs. prompts that encourage long preambles.
- **Using `opening_text` for key beats.** Scripted `opening_text` bypasses the LLM entirely — no LLM call is made when a node has `opening_text`. TTFA for scripted text is ~300ms (ElevenLabs only).
- **Keeping `max_response_length` to 60-100.** Shorter responses finish streaming faster.

If a node has BOTH `opening_text` AND a player action that might generate a long LLM response, consider splitting it into two nodes.

---

## Authoring Checklist

Before handing a node or scenario to the engine:

- [ ] Every `id` in `nodes` matches its own `"id"` field exactly
- [ ] Every `target_node` and `failure_node` points to a node that exists in `nodes`, or is `""` (stay in node)
- [ ] `start_node` exists in `nodes`
- [ ] All `end_nodes` entries exist in `nodes` and have no actions (or the loop won't exit)
- [ ] No node is an island — every non-start, non-end node is reachable from `start_node`
- [ ] `opening_text` is under 80 words
- [ ] `max_response_length` is set to 60–100 for voice-first nodes
- [ ] All `skill_check` values are one of: `strength`, `dexterity`, `constitution`, `intelligence`, `wisdom`, `charisma`
- [ ] Any node with `"is_checkpoint": true` is a stable, meaningful save point (not a transient or fail state)
- [ ] `forbidden_topics` is present on any node near sensitive content
- [ ] Second-person ("you") used throughout all text fields
- [ ] No numbers read aloud in `opening_text` — outcomes are qualitative
- [ ] `calibration_enabled` is only `true` if the scenario explicitly needs Tribal Service stat generation (CALLOUSED does; others don't)
