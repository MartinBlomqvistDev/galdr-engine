# CALLOUSED — Master Design Document v3.0

RPG Proof-of-Concept for GALDR Engine

---

## DOCUMENT HISTORY

- v2.7: Contained prologue structure §10 (5 nodes), human adaptations, settlement specs. Outdated: "The Ribs" (now Vestal), Ven system present, Scav-Silos present, Swedish terminology.
- v2.8: Severely outdated. Missing The Kern. Choke outdated. Ven system present. Settlement named "The Ribs" (now Vestal). Only 5 endings documented. Swedish terminology present.
- v2.9: Major overhaul. Integrates all GPT discussion sessions (White Sea, Singing Ruins ×3, World Discussion ×2, Choke). Writing chronology used for contradiction resolution. Missing prologue structure, human physiology.
- v3.0: Adds §PROLOGUE STRUCTURE (11 nodes, v3.0.0 canonical). Adds §HUMAN PHYSIOLOGY. Expands The Cleft settlement spec. Smart-dust calibration status documented. Prologue rewrite: pods occupied, Cleft intact at prologue end, decontamination moved to midpoint.

**Writing Chronology (contradiction resolution — lowest to highest authority):**

1. White Sea Discussion
2. Singing Ruins Discussions (×3)
3. World Discussion (×2)
4. Choke Discussion

---

## WHAT WAS REMOVED

The following concepts no longer exist in CALLOUSED — not in the world, not in authoring notes, not in any file.

**Ven** — Removed entirely. No disembodied voices. No transmissions. No system narrator. Time is understood through absence.

**The Ribs** — Renamed to Vestal. All prior references superseded.

**Scav-Silos** — Removed as a concept. The Kern is the biome that covers this design space.

**All Swedish terminology (forvaltar-saga, etc.)** — Removed. English throughout. All content, prompts, dice strings, and STT are en-US.

---

## THE STORY'S REAL CORE

**Surface premise:** Find the Ancestors, get them to fix the failing grid.

**Actual premise:** What happens when someone built to survive is forced to decide who gets to live?

This is a steward story, not a hero story. The player is not the savior. They become the system.

**The thematic tension:** Artificial vs. Emergent.

| | Artificial | Emergent |
| --- | --- | --- |
| The system | Designed, optimized, stable | |
| The world | | Chaotic, alive, inefficient |
| The player | Built by the world — but compatible with the system | |

The player is the conflict.

**The Ancestors are not wrong — they are optimizing the wrong goal.** They have correct data (grid collapse within decades, biomes are artificial, surface populations are evolutionary drift from the Maintenance Caste). The decontamination sequence was not their conclusion — it was the system's startup logic, embedded 50,000 years ago, running exactly as designed when initialization finally completed. The math is right. The conclusion is monstrous. No one chose it. There is no villain to blame.

**The Cleansing Protocol was not murder. It was a startup routine.** The Ancestors did not wake up and choose to destroy The Cleft. They woke up and ran an initialization sequence — FACILITY PERIMETER RESET, DECONTAMINATION SEQUENCE: STANDARD — designed 50,000 years ago to clear "biological contamination" from the perimeter before grid operations resumed. The Cleft was inside the perimeter. The system did not know the contamination was people.

**Lo represents meaning. The Ancestors represent survival.** Lo's worldview (tribes = real people, Ancestors = wrong) is emotionally correct but factually incomplete. If the system is destroyed, Lo's world survives — and then slowly dies as the grid fails. There is no clean side.

**The system does not deny access. It makes access non-viable.** There is no gatekeeper. The environment is the gate. The biomes are infrastructure that happens to be lethal. Their barrier effect on humans is secondary, not designed.

**The authentication is not genetic. It is a census count.** The Maintenance Caste revolted 50,000 years ago by permanently removing one unit from the Ancestor registry. The system's startup sequence requires all registered units accounted for — 480/480. With one unit missing, the count permanently reads 479/480. Startup can never complete.

The player authenticates at the terminal not because of biology or lineage — but because they showed up. The player is not special. They were first.

**Previous operators exist in the session log, not in the system.** Others found temporary access windows and entered. Only their changes remain active. "CONCURRENT OPERATORS DETECTED: 0 ACTIVE" is a log entry. Not a ghost.

**The 4-Phase Narrative Arc:**

| Phase | Player state | The lie | What breaks it |
| --- | --- | --- | --- |
| 1 — Ignorance | Hope, direction | "There is a solution that saves everyone" | Contradictions in Worker Logs |
| 2 — Doubt | Unease | "The Ancestors are just sleeping, not dangerous" | The system feels cold |
| 3 — Betrayal (midpoint) | Shock | "I can fix this" | The Cleft is destroyed. The system worked — it just wasn't built for us |
| 4 — Ownership | Weight, responsibility | — | "Which world deserves to exist?" |

---

## PROLOGUE STRUCTURE

**File:** `app/scenarios/calloused_prologue.json`
**Version:** 3.0.0
**Title:** "The Drop"
**Nodes:** 11
**Phase position:** Phase 1 (Ignorance / Hope). Ends with Ancestors alive, Cleft intact, census 479/480.

---

### Design Rules for the Prologue

- Ancestors are **sleeping in occupied pods**. Slow rise and fall of breathing. Fifty thousand years. Still alive.
- The Cleft is **intact** at prologue end. Decontamination belongs at Phase 3 (midpoint), not here.
- The system detects the player but **cannot authenticate**. Census reads 479/480. Startup authorization suspended.
- The player is not special. They were the one who showed up when the Breath stopped.
- Smart-dust calibration is **disabled** (`calibration_enabled: false`). Pending diegetic implementation: the correct design (v2.1) has ancient facility systems scan the player after descent — inside, framed as systems detecting the intruder, not a meta-game tutorial before play begins.

---

### Pressure Budget

**Max path into `lo_aftermath`: 4**

| Node | Pressure delta | Condition |
| --- | --- | --- |
| facility_descent | +1 | always |
| the_dark (fail) | +1 | failed maintenance unit encounter |
| cryo_room (catalog fail) | +1 | failed WIS check when cataloguing pods |
| proximity_auth | +1 | always |

Gold Zone (4–6) is active at `lo_aftermath`. Design target met.

---

### Node Map

**1. crater_investigation** — Glass Crater Basin, dawn. Three days since the Eternal Breath stopped. Player and Lo are on the crater floor together, investigating. Lo crouches five meters ahead, pressing a palm to the obsidian. Both actions lead to the fall — it is not a failure condition, it is the inciting event.
*Actions:* `read_the_ground` (WIS DC 8, success: `felt_the_void`, pressure –1), `call_to_lo` (free, `lo_heard_you_go`)

**2. the_fall** — The obsidian cracks. Player drops through. Hard landing on ceramic. Lo's voice from above, then the crack narrows and the light is gone. Auto-transitions to `the_dark` after 4s.
*Flags set:* `fell_through`; pressure +1

**3. the_dark** — A maintenance cleaning unit running its circuit for 50,000 years. It is not hunting. It is working. Primary lesson: the world is indifferent, not hostile.
*Actions:* `slip_through` (DEX DC 14), `go_still` (WIS DC 12 — PRIMARY LESSON delivery), `charge_at_it` (STR DC 12), `find_the_panel` (INT DC 13)
*All paths:* success → `cryo_room`; failure → `dark_wounded`
*WIS success note:* The system prompt requires this to be delivered clearly — the pattern is fixed, the unit does not know the player is here. This is the game's foundational premise.

**4. dark_wounded** — Mechanical injury. Brief. The unit resumed its circuit. It did not register the interruption. Pressure +1. → `cryo_room`

**5. cryo_room** — Occupied pods. The slow rise and fall of breathing. Fifty thousand years. They are still alive.
*Actions:* `catalog_the_pods` (WIS DC 10 — success: detailed inventory, +1 toward lo_trust; failure: overwhelm, pressure +1), `examine_one_pod` (free → console_chamber), `move_to_the_far_door` (free → console_chamber)

**6. console_chamber** — Terminal active. Blocked.

```text
MAINTENANCE INTERFACE ACTIVE.
OPERATOR AUTHENTICATION REQUIRED.
CENSUS DISCREPANCY: 479 / 480 REGISTERED UNITS.
STARTUP AUTHORIZATION SUSPENDED.
```

*Actions:* `study_the_terminal` (INT DC 13 → `proximity_auth`, success: full terminal read), `take_the_data_card` (free → `proximity_auth`, grants Worker Log Fragment item), `turn_to_leave` (free → `proximity_auth`)

**7. proximity_auth** — The system detects the player. It cannot authenticate.

```text
CLOSEST MC DESCENDANT DETECTED.
AUTHENTICATION PENDING.
CENSUS DISCREPANCY: 479/480.
STARTUP AUTHORIZATION SUSPENDED.
```

Pressure +1. The system has been waiting for 50,000 years for someone to stand here. This is as far as it can go without the count completing.
*Actions:* `leave` (free → `recognition`)

**8. recognition** — Player climbs back out. The shaft. The hatch. The return. "The room changes" — valid for all three incoming paths from console_chamber. The facility does not stop the player. It logs the departure.
*→ `crater_surface`*

**9. crater_surface** — Back at the surface. The Cleft is still there. Obsidian. UV. The scale. Lo is where they left them.
*Flags set:* `saw_the_ancestors: true`. `the_cleft_gone` is NOT set here — correct.
*Opening:* "The Cleft is still there."

**10. lo_aftermath** — Phase 1 conversation. Lo mirrors world state: pressure 4–6, Gold Zone.

*Actions:*

- `tell_lo_what_you_found` (lo_trust ≥ 1): Lo listens fully. lo_trust +1. → `prologue_close`
- `say_nothing` (lo_trust ≥ 1): lo_trust –1. → `prologue_close`
- `stand_alone` (lo_trust = 0): No exchange. → `prologue_close`

*Note:* No confrontation about Cleft destruction — the Cleft is intact. This is Phase 1.

**11. prologue_close** — Phase 1 establishes hope. The Ancestors are sleeping in the dark below. The system has been waiting for 50,000 years. The census count is the key. The player is not special. They were first.

---

## WORLD LAW

**Primary law:** Stability in one place creates instability elsewhere.

The planetary infrastructure was not destroyed. It degraded. Each biome represents a system still trying to fulfill its original function — without coordination, each creates pressure on the others.

There are no safe zones. Biomes cover the whole world as interlocking failure systems. Settlements exist only where two or more systems temporarily cancel each other out. No permanent access routes. Only temporary viability windows.

**World drift is misalignment, not decay.** Some things improve. Some fail. Nothing trends cleanly. The player should sometimes benefit from waiting. Uncertainty prevents optimization.

**Time is understood through absence.** What is no longer there. Who is no longer present. Routes that have closed. Settlements that have changed. No narration announces this. The player notices or does not.

---

## HIDDEN VARIABLES

### world_stability (0–100)

Starting value: 65
Passive decay: ~2–3 per rest cycle equivalent
Player can accelerate or decelerate

**Thresholds:**

- 65–50 (Degrading): Ambient pressure +1 in biomes. Settlements mention instability.
- 50–35 (Straining): First named consequence. A route closes. Lo stops offering alternates.
- 35–20 (Failing): Named settlement consequence. Someone the player met is gone. Treaty ending requires action in this band.
- 20–5 (Collapsing): White Sea unpredictable in real-time. Lo reactive only.
- 5–0 (Terminal): Only Usurper, Severance, and Legend endings available.

---

### accumulation_load (0–100)

Kern-specific. Accumulates from all player actions in The Kern.

**Thresholds:**

- >60: world_stability drains +1 per rest cycle globally
- >80: drain doubles
- ~85: Main Event trigger (The Settling at Vestal)

Main Event result: permanent world_stability –5 to –8 regardless of outcome.

Unique axis: affects world_stability through TIME (what you don't prevent), not through direct action.

---

### carbon_load (0–100)

Choke-specific subtype. UNDER DEVELOPMENT.
Recovery: Char zones, biome edge, reduced movement.

---

### oxygen_level (0–100)

Choke-specific subtype. UNDER DEVELOPMENT.
Recovery: descent only.

---

### pressure (0–10) — Player physiological/cognitive/environmental load

- 0–3: Controlled. Clear narration.
- 4–6: THE GOLD ZONE. Primary design target.
- 7–8: Overload. False confidence. Narrator emotionally wrong. Dangerous paths sound viable.
- 9: Breakdown edge. Reality slips.
- 10: COLLAPSE. Forced failure. No roll.

---

## BIOMES

Six biomes total. Three locked. Two under development. One TBD.

---

### BIOME 1: WHITE SEA
**Status: v1.0 LOCKED**

**Function:** Geological mass redistribution. Upward pressure force. The ground moves.

**Biome law:** Stillness is danger. Movement is the only stability.

**Settlement proximity:** Vestal (boundary — see Settlements)

**World relationship:** White Sea upward geological force + Kern inward convergence pressure = temporary stability at boundary. Primary structural counterforce to The Kern.

---

### BIOME 2: THE SINGING RUINS
**Status: v1.0 LOCKED**

**Function:** Unknown pre-function. Now: acoustic resonance structures. The ruins are still responding to something.

**Biome law:** Prediction is the threat. The Ruins respond to pattern.

---

#### The Slipform

The Slipform is not alive. It does not hunt. It predicts. It tracks movement patterns and strikes when its confidence threshold is reached. Vary movement to break prediction. Repetition is death.

**Two exposure types:**
- Prediction exposure: movement-based. Immediate strike risk when pattern repeats.
- Position exposure: stillness-based. Slow approach. Different danger, different timing.

**Confidence model:** Pattern-tracking based on repetition. Breaking prediction resets confidence but does not guarantee safety.

---

#### Signal Language (6 types)

**Clean Pull** — Smooth directional draw, consistent force. The space wants you to move a specific way. Trust it.

**Micro-Mismatch** — Small inconsistency in pull direction. Barely perceptible. Slipform is building a prediction. Vary movement now.

**Air Pressure Shift** — Sudden pressure change, no directional information. Something nearby changed state. Source unknown.

**Reactive Space** — Environment responding to presence. You have been logged. Not yet acted upon.

**Overload** — Pressure from all directions simultaneously. Slipform confidence critical. Exit current pattern immediately.

**Silence Pocket** — Dead zone in the signal field. No resonance. No prediction possible here. Brief safe ground.

---

#### Contact Corruption

Casual touch does not ground. Drifting begins.
Intentional full-body grounding stops drift and resets contact corruption.

---

#### Narrowing — 5-Phase Authoring Law

Canonical scaffold for all Ruins encounters. All authored sequences must follow this structure.

**Phase 1:** Safe mismatch. No punishment. Player learns signals exist.
**Phase 2:** Loss → interruption by grounding → clarity. NOT a tutorial. Grounding must interrupt failure, not be introduced as a tool before failure occurs.
**Phase 3:** Slipform presence, non-lethal. Player understands what they are navigating.
**Phase 4:** Player must actively break prediction pattern to survive.
**Phase 5:** First moment a strike can land.

---

#### Core Loop (locked)

> Maintain a correct mental map under corrupted acoustic input.

1. Player moves → drift accumulates
2. Subtle inconsistencies appear (echo mismatch, airflow offset, repeated micro-misalignment)
3. Player chooses: ground (safe info, unsafe moment) or continue (faster, risk misalignment)
4. Movement while misaligned → Slipform risk
5. Player corrects → rebuilds map
6. Repeat under increasing pressure

**Primary design rule:** The world is always correct. The player misinterprets it.

**Tone target:** Tense but readable — not hard but fair. Difficulty comes from imperfect information and decision timing, not hidden rules.

---

#### Grounding — Authoring Rules

**Passive contact ≠ active grounding.** Walking along a wall, brushing a surface, or trailing a hand does not cancel drift. The brain still trusts sound over touch during continuous movement. Drift continues.

**Active grounding requires:** stopping or near-stopping movement, applying deliberate pressure, committing attention to physical feedback.

Trigger phrases that ground: "I stop and press against the wall", "I brace myself", "I steady myself and feel the surface", "I crouch and stabilize."

Trigger phrases that do NOT ground: "I brush the wall", "I run my hand along it", "I follow the wall forward."

**Cost (always indirect — never resources or cooldown):**

- Movement stops or slows heavily
- Environmental awareness narrows — Slipform tracking degrades
- Momentum is lost — world continues evolving, threats reposition

**Result:** Grounding is safe information in an unsafe moment. It is never blocked and always accurate. It is never free.

**Frequency target:** Frequent and tactical — part of movement rhythm, not a panic button. Good play looks like: short burst, ground, confirm, move again.

---

#### Slipform — Trigger Conditions (locked)

Slipforms strike only when all three conditions are met simultaneously:
1. Player is moving
2. Player is misaligned (drift active)
3. Player is in exposed space (not inside, not vertical)

They do not patrol. They do not apply ambient pressure. They are the consequence of committed movement in the wrong place — not an independent threat.

**Outcome when triggered:** One decisive event — major pressure spike, forced reposition, or orientation scramble. Not chip damage. Not repeated attacks.

---

#### Failure Ladder (locked)

Failure escalates state, not just outcome. Each tier removes control, adds cost, narrows options.

**Tier 0 — Control (baseline)**
Pressure 3–5. Player has options. Feel: "tense but manageable."

**Tier 1 — Slip (minor failure)**
Triggers: small drift misread, late grounding, minor positioning mistake.
Effects (1–2): slight reroute, pressure +1, lose optimal path.
Feel: "that wasn't clean." Fully recoverable through skill.

**Tier 2 — Disruption (real mistake)**
Triggers: ignoring drift signals, overcommitting to sound, grounding too late or too long.
Effects (2–3): hard reposition into different corridor / level, pressure +2, Slipform enters play space, environmental clarity drops.
Feel: "oh fuck — this got worse." Player still has agency, but under pressure.

**Tier 3 — Cascade (loss of control begins)**
Triggers: repeated mistakes, panic movement, failure while already disrupted.
Effects (2–4): map invalidated (major disorientation), pressure 7–8, multiple threats active (Slipform + terrain), forced movement (fall / shift / displacement), grounding harder to use effectively (contextual, not blocked).
Feel: "I'm not in control anymore." THIS IS THE DREAD ZONE. Tier 3 must be playable — not instant collapse.

**Tier 4 — Collapse (terminal failure)**
Triggers: pressure 9–10, no viable path, failure to recover from Tier 3.
Effects: total spatial loss, narrator factually unreliable, movement reactive only.
Resolution: Ruins People intervention. Must feel like failure, not help.

**Post-collapse consequences (always apply):**

- Major reposition (progress lost)
- Pressure baseline stays elevated (6–7 minimum entering next section)

Plus 1–2 of: tool/resource loss, Lo trust drop (–1), route permanently altered, new hazard introduced.

**Escalation memory:** After Tier 2–3, the next mistake escalates faster and recovery is harder. Failure does not reset cleanly.

**Telegraph requirement:** Player must feel escalation before collapse arrives — worsening sound, Lo hesitation, narrator instability, environment tightening. Collapse must never feel sudden.

---

#### Consequence Selection Model

Do not randomize consequences blindly. Use tiered + contextual selection.

**Severity tier** is set by the failure level (Tier 1 = minor, Tier 4 = collapse).

**Category** is weighted by context — what the player was doing when they failed:

- Moving → position consequence (reroute, reposition)
- Grounding too long → exposure consequence (Slipform repositioned)
- Ignoring signals → state consequence (pressure spike)
- World-level mistake → world consequence (route altered, new hazard)
- Lo-related → Lo consequence (trust drop, behavioral shift)

**Selection:** 1 primary (matches failure type) + 1 secondary (weighted). Never fully random. Always attributable.

---

### BIOME 3: THE KERN
**Status: v1.0 LOCKED**

**Function:** Mass redistribution / waste sequestration / planetary error-correction sink. The world's digestive system.

**Biome law:** Every helpful action creates future risk.

**Identity:** Before degradation: flow infrastructure, no traversable terrain. Now: 50,000 years of unprocessed material = the terrain itself. Pressure-gradient driven. No machinery needed. Physics persists over geological time.

**Unique axis:** Player is the primary cause of danger. In every other biome, the biome is the threat. In The Kern, the player's own accumulated actions are.

**Physical composition:** Debris of other biomes physically present. Choke carbon. White Sea geological mass. Ruins structural fragments.

**Unknown stratum:** At the Hub's deepest layer. Pre-dates the current planetary system. Never explained.

---

#### Player Verbs (5, canonical)

**TEST:** Light interaction before committing. Reveals stability. Costs time. Increases accumulation_load.

**COMMIT:** Fast movement. No information. High risk. Low load cost.

**CUT:** Force new path. Major load increase. Permanently alters future terrain for player and others.

**REDISTRIBUTE:** Shift load elsewhere. Local stability + global risk. High-skill play.

**WAIT:** Observe. Pattern clarity increases. Global load continues accumulating.

---

#### Signal Language (6 types, physical-only)

**Set** — Sudden stillness + new structure forming. Irreversible change just occurred.

**Creep** — Slow shifting edges + tension lines. Delayed movement building. Not happening yet. Will.

**Shear** — Grinding textures + directional stress. Two layers moving against each other.

**Sink Memory** — Layered scars + compressed patterns. This ground has changed before. It knows how.

**Reject** — Unstable clusters + mixed textures resisting integration. System cannot process cleanly. Chain reactions likely.

**Lock** — Sudden stillness after movement + new structure forming. Your action has committed. Cannot be undone.

---

#### Event Structure

Accumulation_load triggers. Not time-based. Action-based.

**Entry:** Safe exploration phase. Teaching environment. No stakes yet.

**Minor Event 1 — "First Shift" (~30 load):**
Terrain reacts after player passes through it. No punishment. No blame. Teaches the core rule: your past actions shape the path forward.

**Minor Event 2 — "Someone Else Pays" (~60 load):**
Route collapse or NPC harm tied to an earlier player path. Not explicitly blamed on the player. Just consequence, visible, carrying no explanation.

**Main Event — "The Settling" (~85 load):**
Occurs at Vestal. Kern convergence overwhelms White Sea counter-pressure. Vestal's stability is destroyed. See Vestal NPC section.

---

#### Carriers (behavioral group, not faction)

Always moving. Follow material flows. Create and abandon paths. Avoid stability zones.

**Function:** Guide accumulation, enable traversal, cause long-term instability.

**Subtypes:**
- Runners: Fast, commit-heavy, destabilizing. Short-term path creation, long-term damage.
- Balancers: Redistribute-focused, system-aware. Still cause damage — just distributed.

**Relationship to Vestal:** Mutual dependence and mutual harm. Neither can exist cleanly without the other.

**During The Settling:** Carriers move out. They do not try to save Vestal. They knew.

**Carrier Encounters (sequential — teaching curve, NOT alternative paths):**

*Encounter 1 — The Crosser:* Observational. Player watches a Carrier navigate. Learns Carrier logic from movement alone. The path the Crosser takes becomes a failure point in a later sequence.

*Encounter 2 — The Trade:* Moral temptation. A faster, unstable route is offered. Immediate gain. Future consequence. No explicit warning.

---

#### The Hub

**Access:** Only aligns after The Settling. The cascade from Vestal's collapse changes the pressure map. Before The Settling: inaccessible.

**Structure:**

*Layer 1 — The Recognizable:* Compressed debris from other biomes. Player identifies objects from places they have been.

*Layer 2 — The Record:* Most complete Vault. Correction logs embedded in the material. The grid's attempts to fix itself, preserved in physical form.

*Layer 3 — Still-Functional Node:* Last active correction mechanism. Still processing something pre-cataclysm.

Player choices at Layer 3:
- Leave it alone
- Extract it
- Attempt reactivation

All three create different consequences. None are clean.

*Unknown stratum (deepest):* Pre-dates the current system. No explanation. Never given one.

---

### BIOME 4: THE CHOKE
**Status: UNDER DEVELOPMENT**

*Discussion ongoing. All content below reflects current design state and is subject to revision.*

**Function:** Biochar production via incomplete combustion. Carbon sequestration through controlled burn. When functioning correctly: not CO2 release.

**Biome statement:** "The fire is not wrong. You're standing in the wrong place."

**The 35% O2 Paradox:**
Atmospheric oxygen is approximately 35%. High oxygen = hotter fires = more complete combustion = CO2, not char. The system was designed to hold burn temperature in a specific range. Degradation = temperature desynch = net carbon release.

**Core tension:** The correct response to fire in The Choke is almost never suppression.

---

#### Human Adaptation (50,000 years at 35% O2)

- Lean, low-fat body composition
- Slower resting breathing rate
- High CO2 tolerance
- Smaller, denser lungs
- Larger irises
- Heat-resistant skin
- Structural particulate filtration

**CRITICAL:** Choke-natives cannot tolerate 21% O2. Going underground (lower O2 pressure) = hypoxic crisis. Their adaptation locks them out of the underground burn chambers.

**Above-canopy exposure stages:**
- Stage 1: Euphoria
- Stage 2: Dysfunction
- Stage 3: Seizure / collapse

**Player advantage (non-native):** Player's unspecialized biology is the access key underground. Choke-natives cannot go deep. Player can.

---

#### Signal Language (6 types, UNDER DEVELOPMENT)

**Char** — Ground darkened, texture changed. Biochar forming correctly. Good ground.

**Resin Build** — Sticky, viscous pressure on surfaces. Fire approaching wrong temperature range.

**Crawler Convergence** — Movement patterns in the canopy. Slag-Crawlers redirecting. Follow them.

**Vent Bloom** — Sudden pressure from below. Vent active. UNDER DEVELOPMENT.

**Dead Air** — Total stillness. No particulate movement. Precursor to Carbon Lock.

**The Crack** — Structural fracture in biochar substrate. Load-bearing failure imminent.

---

#### Player Verbs (5, UNDER DEVELOPMENT)

**HOLD POSITION** — Don't move. Wait for cycle.
**PUSH THROUGH** — Commit. High risk.
**FOLLOW THE CRAWLERS** — Defer to Slag-Crawler movement patterns.
**CONTROLLED EXPOSURE** — Partial entry into fire zone.
**VENT-TRIGGER** — UNDER DEVELOPMENT.

---

#### Fauna (UNDER DEVELOPMENT)

**The Slab** — 6m arthropod. Indifference dread. Does not register the player as significant. That is the horror.

**The Draft** — 3m dragonfly. Impaired dread. Something is wrong with it. It moves wrong.

**The Stitch** — Emergence dread. Dozens emerge after Carbon Lock. Not visible until already present.

---

#### Slag-Crawlers

Revelation flag: **knows_crawlers_deployed**

Not natural fauna. Designed. Deployed as an emergency measure when plant sequestration failed. Maintenance infrastructure. Still doing their job.

---

#### Underground Burn Chambers

Built by the Maintenance Caste. Approximately 50,000 years old.

Choke-natives cannot go deep — their 35% O2 adaptation makes low-O2 environments hypoxic. The chambers have been sealed from the surface population for generations, not by intention but by biology.

**Underground navigation:** Acoustic. Hearing the burn cycle through rock. Unique to underground Choke. Does not overlap with The Kern's signal language.

---

#### Behavioral Groups (UNDER DEVELOPMENT)

**Cycle Walkers** — Move with the burn cycle. Anticipatory. Know when to be where.
**Crawler Guides** — Work with Slag-Crawlers. Intermediary function.
**Lung Burners** — UNDER DEVELOPMENT.

---

#### Lo in The Choke

Lo is Choke-native. Lo is an expert here. Lo knows fire and cycle correctly. Lo does not go wrong within the biome.

**Lo's vulnerability:** Above canopy only. The Lung event. Above-canopy exposure affects Lo first. Player may need to navigate without Lo's guidance during this window.

**Carbon Lock — Lo's role (UNDER DEVELOPMENT):**
Dead Air precursor → Lo moves INTO the fire (correct response) → player decision: FOLLOW / OVERRIDE / LET GO.
Lo can be maimed at Carbon Lock if player overrides.

---

#### 5 Anchor Events (UNDER DEVELOPMENT)

1. **The Lung** — Above-canopy event. Lo's vulnerability. Player without expert guidance.
2. **The Guide** — UNDER DEVELOPMENT.
3. **The Long Wait** — UNDER DEVELOPMENT.
4. **The Dead Corridor** — UNDER DEVELOPMENT.
5. **The Carbon Lock** — Main event. Dead Air → Lo moves into fire → FOLLOW / OVERRIDE / LET GO.

---

#### Learning Arc

Beat 1: Player suppresses fire → worse outcome.
Beat 2: Wrong burn temperature → ash, not char.
Beat 3: Carbon Lock → char forming correctly. Lo: "This is good ground."

---

#### Hidden Ending: The Clearing

Requires: **submit_burn_authorization** flag + additional conditions (UNDER DEVELOPMENT).

---

#### Choke-Specific Base Ending

**Status: MISSING — UNDER DEVELOPMENT**

A Choke specialist path exists in design but has no dedicated ending. Currently slides into Retreat (D). Needs its own ending. Design begins after Choke discussion completes.

---

### BIOME 5: GLASS CRATER
**Status: UNDER DEVELOPMENT**

**Role:** Aftermath biome. A scar. Graveyard of function.

**Core identity:** A place defined by what happened, not what is happening. The system here did not degrade — it ended.

**Core mechanic direction:** Surviving collapse, not understanding system. Player navigates consequence, not cause.

**Settlement proximity:** The Cleft (UNDER DEVELOPMENT — see Settlements)

---

## HUMAN PHYSIOLOGY

50,000 years of biome pressure on the Maintenance Caste's descendants. Three major adaptations across the surface population. These are not uniform — populations near specific biomes carry specific traits. The player has an unspecialized body (generalist, less locally optimized). This is their advantage.

---

### Dermal Carapace

Exposure to Kern particulate and White Sea geological abrasion over generations. Dense, thickened skin over load-bearing surfaces — hands, forearms, soles, outer shoulders. Tactile sensitivity reduced in calloused zones; elevated in uncalloused (inner wrist, throat, face).

**Gameplay consequence:** Player touch-based perception favors uncalloused contact. Full-body grounding in the Ruins requires deliberate commitment — not habit.

---

### Acoustic Vulnerability

Sustained exposure to the Singing Ruins' resonance field causes lasting auditory drift. Ruins-proximate populations show degraded signal discrimination — too much pattern-matching compensation has overtuned the noise filter. They move through the Ruins by contact and habit, not signal reading.

**Gameplay consequence:** Player is not adapted — fresh signal sensitivity is an advantage and a vulnerability simultaneously. The Ruins will affect the player more acutely on first exposure. Recovery is faster precisely because there is no pre-burned-in compensation to unlearn.

---

### Adrenaline Crash

After extreme physiological stress — sustained pressure, major exertion, near-death — the body shuts down involuntarily. Not collapsing. Not unconsciousness. A full-body reset: hands stop shaking, vision clears, movement becomes deliberate. Lasts minutes. What follows is calm that does not match the situation.

**Design note:** The crash is not a weakness. The world treats it as normal. It is not treated as dramatic. Lo has seen it before. The only danger is what the player might decide in that window of false calm.

---

## SETTLEMENTS

Settlements exist only where two or more planetary systems temporarily cancel each other out. No settlement is permanent. No settlement is safe.

**Settlement design rules:**
- No faction names
- No profession labels
- Only repeated behaviors
- Social tension = survival disagreement, not ideology
- Roles emerge from behavior, never defined
- Player is not special. Same species. Less locally optimized. Behavioral flexibility is the advantage, not biology.
- Settlements change through absence — missing people, closed stalls, altered routes — not through exposition

---

### VESTAL
**Status: v1.0 LOCKED**

*Formerly: The Ribs. All prior references superseded.*

**Location:** Boundary between The Kern and the White Sea.

**Stability mechanism:** White Sea upward geological force + Kern inward convergence pressure cancel each other at the boundary = temporary stability.

**Main Event consequence:** When accumulation_load reaches ~85, Kern convergence overwhelms the White Sea counter-pressure. The two systems that held Vestal in equilibrium now work together against it.

---

#### Vestal NPC — Combined Reader / Debt

**Behavioral signature:** Always presses palm flat to ground before stepping. Others wait and follow.

**Connection arc:**

First time player uses TEST: this person glances, then mirrors the gesture. No verbal acknowledgment.

Later: they TEST first. Player follows.

**Minor Event 1:** Player can save them from a small collapse. Not framed as significant. Easily missed.

If saved: they are in Vestal when player returns. Small behavioral acknowledgment. No verbal recognition.

**Main Event (The Settling):** They hesitate, trying to reconcile what they feel with what they expect. The terrain is altered by the player's accumulated load. They trust the ground the player changed. They die.

**Aftermath:** When player uses TEST in Vestal after The Settling, there is no feedback. Or delayed feedback. Or false feedback. The verb becomes grief.

*This NPC fuses Reader (recognition through repeated contact) and Debt (structural causality — saved once, killed by accumulation). Recognition and causality arrive simultaneously.*

---

### THE CLEFT
**Status: UNDER DEVELOPMENT**

**Location:** Adjacent to Glass Crater. The settlement sits at the crater rim — built into the cliff walls, partially underground, using the crater's residual geothermal gradient for heat.

**Stability mechanism:** The Eternal Breath (geothermal thermal venting) historically made the crater floor uninhabitable, creating a negative-pressure buffer that kept larger fauna away from the rim settlement. The Breath's cessation is the prologue event — three days of silence for the first time in living memory.

**Relationship to the Ancestor Facility:** The Cleft does not know what is below them. The facility predates the settlement by 50,000 years. The Eternal Breath masked all acoustic and thermal signatures from below. The grid-reader's two-season estimate is the precipitating crisis.

**Fate:** Destroyed at Phase 3 (midpoint) by the Cleansing Protocol — the Ancestor system's startup routine FACILITY PERIMETER RESET. The Cleft was inside the perimeter. The system did not know the contamination was people. This is not a villain's act. It is a startup routine.

**Design rule:** The Cleft's destruction must land as tragedy, not twist. Phase 1 establishes attachment (Lo, recognition). Phase 2 introduces doubt (system feels cold). Phase 3 delivers the event. Players who have been paying attention will have felt it coming. Players who were not will feel it as ambush — both responses are correct.

**What survives:** Everyone who was not at the rim when the sequence ran. Lo and the player survive because they were in the crater. The census of survivors is the opening condition of Phase 4.

---

### THE VENT
**Status: TBD**

**Location:** UNDER DEVELOPMENT.

**Current question:** Keep, rename, or cut entirely. The Vent was originally a geothermal access point settlement — a community built around a stable, directional thermal output. With The Kern and White Sea covering the geological pressure design space, and The Cleft covering the "geothermal-adjacent rim settlement" space, The Vent's niche is unclear. Decision pending after Choke and Glass Crater development completes.

---

## THE COMPANION — LO

Lo is the player's primary companion. Lo is not a guide. Lo is a world-state mirror.

**Core rule:** Lo's behavior reflects the state of the world, not the emotional state of the player.

**Lo trust scale: 0–5**

**Lo behavior by world_stability:**

- High: Lo anticipates. Makes choices before player asks. Proactive.
- Mid: Lo follows more. Fewer proactive actions. Responsive.
- Low: Lo hesitates. Delayed reactions.
- Critical: Lo reactive only. Commits late, or commits wrong.

**Lo sacrificial distraction mechanic:** Exists. Dynamic. Will not be canonized with specific trigger conditions. If it becomes predictable, it fails emotionally.

**Lo in The Choke:** Expert. Choke-native. Lo's instincts here are correct. Lo's vulnerability is above canopy only.

---

## PLAYER PLAYSTYLES

Three behavioral playstyles. Accumulate through observed behavior. No menu choice. Player is never told their type.

**Anchor** — Stabilizes. Tends toward Operator ending.
**Flow** — Moves through. Tends toward Usurper ending.
**Listener** — Waits and receives. Tends toward Treaty ending.

**Rule:** Exceptions must exist. Behavioral predisposition can be resisted. No clean lock until late game.

**Contradiction requirement:** Meaningful endings require players to act against type at least once.

---

## ENDINGS

Total distinct experiences: approximately 19.

---

### Base Endings (5)

**A — Operator**
The player took the world apart to understand it. The understanding cost more than the world could absorb. But the player knows. Tends toward: Anchor.

**B — Usurper**
The player moved into the space left by what failed. Not rebuilding. Occupying. A new equilibrium, unstable, theirs. Tends toward: Flow.

**C — Treaty**
Negotiated outcome. Something preserved. Something surrendered. Requires action in world_stability band 35–20. Tends toward: Listener.

**D — Severance / Retreat**
The player left. Some things survive without the player in them.

**E — Collapse / Legend**
The player broke something that cannot be fixed. Becomes story. Cautionary or mythic depending on final framing.

---

### Hidden / Rare Endings (5)

**The Maintenance Returns**
The still-functional node at Hub Layer 3 is successfully reactivated. Something broken for 50,000 years begins working again. The player will not live to see what it does.
Conditions: UNDER DEVELOPMENT.

**The Inheritance**
Something passes from the player to a specific person. Not the world. What they inherit, they may not want.
Conditions: UNDER DEVELOPMENT.

**The Weight of Lo**
Requires Lo to have been sacrificed, maimed, lost, or abandoned at some point. Lo trust at a specific value at game end. The weight is not Lo's.
Conditions: UNDER DEVELOPMENT.

**The Correct Math**
All variables balance. The player found the equilibrium. It is technically perfect and it is unbearable.
Conditions: UNDER DEVELOPMENT.

**The Balance**
Rarest ending. Requires acting against behavioral type repeatedly and correctly across multiple biomes. The world does not improve. It holds.
Conditions: UNDER DEVELOPMENT.

---

### Failure State

**The Burial**
Not counted as an ending. A final screen. The player did not fail at the game. The player did not survive the world.

---

### Choke-Specific Ending

**Status: MISSING — UNDER DEVELOPMENT**

Currently slides into Retreat (D). Needs its own ending.

---

## TIME AND WORLD STATE

No global narrator. No system voice. No radio transmission layer.

**Time communicated through:**
- Settlement change (missing people, closed stalls, altered routes)
- Route loss
- Lo behavioral shift
- What is no longer there

**Rest events** deliver specific world consequences. Named places. Named people. Routes that were open.

---

## TECHNICAL NOTES

**Engine:** GALDR (async AI orchestration, voice-first, no LangChain)
**Voice:** STT en-US. TTS pipeline. All interaction voice-only.
**State:** Pydantic v2. All mutations fail loudly.
**Dice:** D&D 5e-flavoured skill checks gate all state mutations before LLM generation. Failed checks branch story. LLM never called on a failed path.

**Smart-dust calibration:**
Status: `calibration_enabled: false` in calloused_prologue.json. Disabled pending diegetic implementation.
Correct design (v2.1): calibration fires inside the facility after descent, framed as ancient systems scanning the intruder. Voice: "The air changes. Something in the walls is reading you." Player answers the Registry's questions in-world. Not before game start. Implementation requires voice_play.py modification to trigger calibration after `facility_descent` opening_text.

**calloused.json — pending cleanup:**

- crater_morning node: remove Ven references
- ancestor_corridor node: remove Ven references

---

*CALLOUSED Master v3.0*
*Biomes locked: White Sea, Singing Ruins, The Kern*
*Biomes under development: The Choke, Glass Crater*
*Settlements locked: Vestal*
*Settlements under development: The Cleft*
*Settlements TBD: The Vent*
*Prologue: v3.0.0 canonical (app/scenarios/calloused_prologue.json)*
*Endings under development: Choke-specific path, all hidden endings*
