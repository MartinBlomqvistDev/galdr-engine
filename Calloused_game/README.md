# Calloused

A voice-first interactive story built on the GALDR Engine. No screen. No GUI. Just sound.

---

## Premise

The player wakes at the bottom of a shaft. The surface is 70 metres up. Somewhere below: hundreds of sleeping Ancestors, a civilization 50,000 years dormant, and a facility grid that is failing.

479 of 480 registered descendants of the Missionaries of the Covenant are alive on the surface. The player is one of them. The terminal at the bottom of the shaft authenticates the player not because of lineage; because they showed up first.

This is a steward story, not a hero story. The player becomes the system.

---

## Status

**Prologue complete** (v3.2.0): 22 nodes, full RPG mechanics, diegetic stat emergence, voice-only playback.

66-test suite covering graph integrity, intent matching, pressure budget, prompt director, and the diegetic stat system. All passing.

Act 1 (overland travel to The Cleft, Lo as guide) is in design.

---

## Running

From the `galdr-engine/` root:

```bash
python app/voice_play.py --scenario app/scenarios/calloused_prologue.json
```

Requires Azure credentials in `.env` and a microphone. See `app/README.md` for full setup.

---

## Mechanics

- D&D 5e-flavoured skill checks gate all state mutations before the LLM generates
- Pressure (0-10): tracks psychological state; affects narrator register at 4, 7, and 10
- Lo trust (0-5): companion relationship; Lo leaves at 0
- Inventory: strictly enforced; LLM cannot invent items the player does not hold
- Diegetic stat emergence: every action carries `stat_weights`; weights accumulate across the prologue; D&D 5e standard array (15/14/13/12/10/8) assigned at prologue close by rank
- Checkpoint saves on designated nodes ("Neural Sync")

---

## Voice

Narrator: `en-GB-RyanNeural` (Azure Speech)

Each node has authored `VoiceParams`: emotion, tempo, reverb. Two-layer tonality: the authored voice sets the acoustic delivery (TTS); game state (pressure, lo_trust, flags) shapes the LLM's narrative register.

---

## World notes

The 479/480 count is a surface census: registered descendants of the Maintenance Caste on the surface. It is not a pod count. The cryo facility holds hundreds of separate Ancestors; two completely distinct populations.

The Cleansing Protocol is not murder. It is a startup routine embedded 50,000 years ago, designed to clear biological contamination from the facility perimeter before grid operations resumed. The system did not know the contamination was people.

There is no villain. The math is right. The conclusion is monstrous.

---

## Files

| File | Purpose |
|------|---------|
| `calloused_master.md` | Master design document (world, narrative arc, factions) |
| `dev_log.md` | Development log; all design decisions and benchmark results |
| `SCENARIO_AUTHORING_GUIDE.md` | How to author nodes, actions, conditions, consequences |
| `app/scenarios/calloused_prologue.json` | Canonical prologue scenario |
