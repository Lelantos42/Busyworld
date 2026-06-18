# Busyworld Architecture

Busyworld is split into two processes that mirror a multiplayer game's
client/server model — one authoritative world, many independent minds.

## The two halves

### Godot (the town) — authoritative for space & time
- Renders the world, runs the day/night clock, owns every citizen's **position**.
- Pathfinds with an `AStarGrid2D` baked from the town's collision rectangles, so
  citizens route *around* buildings and props (no "you hit a wall" — movement is
  solved for them).
- Runs a **decision loop** that paces how often each citizen thinks (so slow model
  calls never stutter the 60fps world) and dispatches the actions that come back.
- Builds perception, shows speech bubbles, handles the camera, HUD and the
  "ask your town" box.

Key scripts (`godot/scripts/`):

| file | role |
|------|------|
| `World.gd` | orchestrator: town build, nav grid, clock, decision loop, perception, action dispatch, day/night, screenshots |
| `Agent.gd` | one citizen's body: animated sprite, nameplate, speech bubble, path-following movement |
| `TownBuilder.gd` | reads `town_layout.json` → ground sprite, Y-sorted buildings/props, solid cells |
| `CharacterFrames.gd` | slices a LimeZu premade sheet into idle/walk × 4 directions |
| `Net.gd` (autoload) | WebSocket client to the brain |
| `GameConfig.gd` (autoload) | loads config, parses CLI flags |
| `HUD.gd` | status bar, event log, request box, citizen inspector |

### Python brain (the minds) — authoritative for thought, memory & economy
- A WebSocket server (`brain/server.py`) that the town connects to.
- For each `decide` request it runs `mind.decide()`: build a prompt from the World
  Guide + the citizen's identity + persistent memories + the live perception → ask
  that citizen's **Ollama** model → parse the JSON action → write new memories →
  pay coin incentives.
- Persists everything to SQLite (`brain/memory.py`) so citizens resume their lives
  across restarts.

## The protocol (JSON over WebSocket)

The town connects to `ws://host:port` (default `127.0.0.1:8765`).

**Town → brain**
```jsonc
{ "type": "hello", "world": "Busyworld", "active": ["mayor","baker",…], "time": "08:30" }

{ "type": "decide", "agent_id": "baker",
  "perception": { … see WORLD_GUIDE.md … },
  "image": "<base64 png, optional, for vision models>" }

{ "type": "player_request", "text": "open a bakery stall in the plaza" }
```

**Brain → town**
```jsonc
{ "type": "action", "agent_id": "baker",
  "thought": "…", "say": "…", "mood": "cheerful", "goal": "…",
  "action": { "type": "work" } }              // type ∈ work|go_home|move_to|wander|talk_to|idle

{ "type": "say",        "agent_id": "mayor", "text": "…" }      // unsolicited speech
{ "type": "agent_state","agent_id": "baker", "money": 107, "goal": "…" }
{ "type": "treasury",   "amount": 507 }
{ "type": "announce",   "text": "[town directive] …" }          // → event log
```

Decisions are dispatched as background tasks on the brain, so one slow model never
blocks the others, and the town keeps animating while it waits.

## Why split authority this way?

A single authoritative *world* (Godot) keeps the simulation consistent — there is
exactly one town, one set of positions, one clock. The *minds* are deliberately
decoupled and distributable: each can live on its own machine, think at its own
pace, and be swapped or upgraded without touching the world. This is what lets the
town scale out across many computers, and what makes each citizen feel like it is
genuinely *inhabiting* the world rather than puppeteering it.

## Pacing & fallback

- Each citizen re-thinks on an interval (and whenever it finishes moving). A
  request in flight has a deadline; if a model is too slow, the citizen is allowed
  to think again rather than freeze.
- If the brain is **unreachable**, the town runs `World.gd`'s local heuristic so it
  is still alive. If the brain is reachable but a single **model** is unreachable,
  `mind.decide()` substitutes its own heuristic for that citizen only.

## Regenerating the town

`tools/build_town.py` is the single source of truth for layout. It bakes the
ground texture and writes `godot/data/town_layout.json` (buildings, props, named
places, collisions, homes, spawn). Both the in-engine town and the fast Python
preview (`tools/_montages/town_preview.png`) are built from this same data, so you
can iterate on the layout without launching the engine.
