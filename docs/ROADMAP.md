# Busyworld Roadmap

Where the town is headed, and how today's architecture already supports it.

## ✅ Milestone 0 — A living town (done)
- Pixel-art town, day/night, 12 citizens with essential roles.
- Local-LLM minds via Ollama, one endpoint per citizen.
- Embodied perception, spatial awareness, conversation.
- Persistent memory (SQLite) — citizens live indefinitely.
- "Ask your town" directives + a coin/treasury incentive loop.
- **Enterable interiors** with animated doors; citizens go indoors to work/rest.
- Cross-platform; runs with or without models.

## ◐ Milestone 1 — Richer inner lives (in progress)
- ✅ **Relationships**: citizens warm to whoever they talk with; friends/rivals
  surface in their prompts and persist.
- ✅ **Needs**: hunger + a town food larder; eating at home/inn; the founder
  provides food and virtual coins.
- ✅ **Reflection**: nightly, the day's events fold into long-term memory.
- ☐ **Better dialogue**: true two-party exchanges when citizens meet (the brain
  already knows who is within earshot), shown as back-and-forth bubbles.
- ☐ **Schedules**: fuller daily routines and money pressure shaping behavior.

## ◐ Milestone 2 — Real eyesight (plumbing done)
- ✅ Godot renders a vision-citizen's local view to a PNG and the brain attaches it
  to that citizen's prompt for **vision models** (`vision: true` in `agents.yaml`).
- ☐ Tune POV framing; have citizens visibly act on what they *see* (aesthetics,
  crowds, distance to a door) rather than only on the structured perception.

## Milestone 3 — Reaching the internet
- Add brain-side **tools** the minds can call ("look up", "fetch", "post"),
  dispatched by the brain and returned as perception. The town stays local-first;
  only the brain talks outward, under your control.
- Example: the shopkeeper checks real prices; the artist pulls a reference image.

## Milestone 4 — Real enterprises & real money
- Promote the **enterprise scaffold** (`brain/memory.py: enterprises`) into live
  ventures: a citizen-run store backed by a real storefront/API (e.g. a print-on-
  demand shop, a digital-goods listing, a service desk).
- The brain exposes safe, auditable **business tools** (list a product, fulfil an
  order, report revenue). Real revenue flows back as treasury, and the founder
  hands out real-money-weighted incentives to the citizens who earned it.
- *Requires your accounts, API keys and explicit opt-in. Nothing financial is
  enabled by default.*

## Milestone 5 — Growth: districts, towns, cities, countries
- **Streaming world**: split the map into chunks/districts loaded around the
  camera so the world can be far larger than one screen or one town.
- **Many towns**: run several `World`s sharing one brain (the `--world` name keys a
  separate SQLite); add roads/travel between them.
- **Population scaling**: tiered minds — a few "hero" citizens on strong models,
  many "extras" on tiny/shared models or pure heuristics, promoted to full minds
  when the player engages them.
- **Hierarchy**: mayors → regional councils → a national layer, each an agent that
  summarizes and directs the layer below. The authoritative-world + distributed-
  minds split is what makes this tractable.

## Milestone 6 — Distributed by hardware
- A turnkey way to register a machine (or Raspberry Pi) as "citizen N's brain":
  it runs Ollama, announces itself, and the brain server routes that citizen's
  thoughts to it. Today this is a manual entry in `agents.yaml`; the goal is
  auto-discovery and health-checks, so adding a Pi adds a citizen.

---

### Guiding principles
1. **Local-first.** Minds run on your hardware; only the brain may reach outward.
2. **One authoritative world.** Exactly one source of truth for space and time.
3. **Minds are replaceable and distributable.** Any citizen can move machines,
   change models, or drop to instinct without breaking the town.
4. **Everything persists.** A citizen's life is data, not a context window.
