"""The mind of a citizen: perception -> decision, with memory + incentives.

decide() is the heart of the brain. It builds a prompt from the World Guide, the
citizen's identity and persistent memories, and the current perception; asks the
citizen's Ollama model what to do; parses the JSON action; writes new memories;
and pays out coin incentives for advancing the founder's requests. If the model is
unreachable, it produces a believable heuristic decision instead.
"""
from __future__ import annotations
import json
import os
import random
import re
from typing import Any

from config import Citizen
from memory import Memory
import ollama_client as oll

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE_PATH = os.path.join(os.path.dirname(HERE), "docs", "WORLD_GUIDE.md")

ALLOWED_ACTIONS = {"work", "go_home", "move_to", "wander", "talk_to", "idle"}

with open(GUIDE_PATH, "r", encoding="utf-8") as _fh:
    WORLD_GUIDE = _fh.read()


def _system_prompt(c: Citizen, mem: Memory, directives: list[str]) -> str:
    recent = mem.recent_memories(c.id, 8)
    facts = mem.important_facts(c.id, 6)
    state = mem.agent(c.id)
    goal = state.get("goal") or (c.goals[0] if c.goals else "live a good life")
    hunger = mem.hunger(c.id)
    coins = state.get("coins", 100)
    food = mem.food()
    friends = mem.friends(c.id, 4)
    hunger_word = ("starving" if hunger > 80 else "very hungry" if hunger > 60
                   else "peckish" if hunger > 40 else "well-fed")
    parts = [
        WORLD_GUIDE,
        "\n\n# Who you are\n",
        f"You are {c.name}, the {c.title} of Busyworld. {c.personality}\n",
        f"Your home is {c.home}. Your workplace is {c.workplace}.\n",
        f"Your lasting goal right now: {goal}\n",
        "\n# Your body & purse\n",
        f"- You feel {hunger_word} (hunger {int(hunger)}/100). Eat at your home or The Inn when food is in the town stores.\n",
        f"- You have {int(coins)} coins. The town's larder holds {food} meals (the founder restocks it).\n",
    ]
    if friends:
        rel = ", ".join(f"{n} ({'friend' if s > 15 else 'rival' if s < -15 else 'acquaintance'})"
                        for n, s in friends)
        parts.append(f"- People you know: {rel}\n")
    if facts:
        parts.append("\n# Things you know\n" + "\n".join(f"- {f}" for f in facts) + "\n")
    if recent:
        parts.append("\n# Recently\n" + "\n".join(f"- {r}" for r in recent) + "\n")
    if directives:
        parts.append("\n# The founder's standing requests\n"
                     + "\n".join(f"- {d}" for d in directives)
                     + "\nAdvance these through your role when you sensibly can.\n")
    return "".join(parts)


def _user_prompt(perception: dict[str, Any]) -> str:
    return (
        "Here is what you sense right now:\n```json\n"
        + json.dumps(perception, ensure_ascii=False, indent=1)
        + "\n```\n"
        "Decide what you do next. Respond with ONLY a single JSON object with keys: "
        "thought, say (optional), action {type, ...}, mood (optional), "
        "remember (optional), goal (optional)."
    )


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # strip code fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # fall back to first balanced {...}
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break
    return {}


def _normalize(decision: dict[str, Any]) -> dict[str, Any]:
    act = decision.get("action", {})
    if isinstance(act, str):
        act = {"type": act}
    if not isinstance(act, dict):
        act = {}
    atype = str(act.get("type", "idle")).lower()
    if atype not in ALLOWED_ACTIONS:
        atype = "idle"
    act["type"] = atype
    decision["action"] = act
    return decision


async def decide(c: Citizen, perception: dict[str, Any], mem: Memory,
                 directives: list[str], image_b64: str | None = None) -> list[dict[str, Any]]:
    """Return a list of messages to send to the game client."""
    mem.ensure_agent(c.id, c.name, c.role, c.goals[0] if c.goals else "")
    decision: dict[str, Any] = {}
    used_model = False
    try:
        messages = [
            {"role": "system", "content": _system_prompt(c, mem, directives)},
            {"role": "user", "content": _user_prompt(perception)},
        ]
        model = c.model_vision if (c.vision and image_b64 and c.model_vision) else c.model
        reply = await oll.chat(
            c.base_url, model, messages,
            temperature=c.temperature, timeout=c.timeout,
            images=[image_b64] if (c.vision and image_b64) else None,
        )
        decision = _extract_json(reply)
        used_model = bool(decision)
    except oll.OllamaError:
        decision = {}
    except Exception:
        decision = {}

    if not decision:
        decision = _heuristic(c, perception, directives, mem.hunger(c.id))

    decision = _normalize(decision)

    # ---- needs: hunger, eating, the town larder ----------------------
    self_p = perception.get("self", {})
    hunger = mem.hunger(c.id) + 4.0
    loc = str(self_p.get("at", "")).lower()
    at_food_place = self_p.get("indoors") and (c.home.lower() in loc or "inn" in loc)
    if at_food_place and hunger > 40 and mem.food() > 0:
        mem.add_food(-1)
        hunger = max(0.0, hunger - 45.0)
        mem.remember(c.id, "Had a meal at home.", kind="event")
    mem.set_hunger(c.id, hunger)
    if hunger > 75 and not decision.get("mood"):
        decision["mood"] = "hungry"

    # ---- relationships: warm to whoever is right beside you ----------
    for p in perception.get("nearby_people", []):
        if p.get("can_talk"):
            delta = 2 if decision.get("say") else 1
            mem.adjust_relationship(c.id, p.get("name", ""), delta)

    # ---- nightly reflection into long-term memory --------------------
    if perception.get("phase") == "night" and self_p.get("indoors"):
        recents = perception.get("recent_events", [])
        if recents:
            mem.remember(c.id, "Reflecting tonight: " + "; ".join(recents[-2:]),
                         kind="fact", importance=2)

    # ---- persist the inner life --------------------------------------
    if decision.get("thought"):
        mem.remember(c.id, f"(thought) {decision['thought']}", kind="journal")
    if decision.get("say"):
        mem.remember(c.id, f"I said: \"{decision['say']}\"", kind="dialogue")
    if decision.get("remember"):
        mem.remember(c.id, str(decision["remember"]), kind="fact", importance=3)
    goal = decision.get("goal")
    mood = decision.get("mood")
    if goal or mood:
        mem.update_agent(c.id, goal=goal, mood=mood)
    else:
        mem.update_agent(c.id)
    # remember events we just perceived so they enter long-term memory
    for ev in perception.get("recent_events", [])[-2:]:
        mem.remember(c.id, ev, kind="event")

    out: list[dict[str, Any]] = []
    msg = {"type": "action", "agent_id": c.id}
    for k in ("thought", "say", "goal", "mood"):
        if decision.get(k):
            msg[k] = decision[k]
    msg["action"] = decision["action"]
    out.append(msg)

    # ---- incentives: reward work that advances the founder's requests --
    coins = _incentive(c, decision, directives)
    if coins > 0:
        bal = mem.add_coins(c.id, coins, "advancing the founder's request")
        treas = mem.treasury() + coins
        mem.set_treasury(treas)
        out.append({"type": "agent_state", "agent_id": c.id, "money": bal,
                    "goal": mem.agent(c.id).get("goal", "")})
        out.append({"type": "treasury", "amount": treas})
    else:
        out.append({"type": "agent_state", "agent_id": c.id,
                    "money": mem.agent(c.id).get("coins", 100),
                    "goal": mem.agent(c.id).get("goal", "")})
    out.append({"used_model": used_model})  # internal marker (server strips)
    return out


def _incentive(c: Citizen, decision: dict[str, Any], directives: list[str]) -> int:
    if not directives:
        return 0
    if decision["action"]["type"] != "work":
        return 0
    text = " ".join(directives).lower()
    relevant = c.role in text or (c.workplace or "").lower() in text
    base = random.randint(2, 5)
    return base + (4 if relevant else 0)


# ---------------------------------------------------------------------------
def _heuristic(c: Citizen, perception: dict[str, Any], directives: list[str],
               hunger: float = 20.0) -> dict[str, Any]:
    phase = perception.get("phase", "midday")
    self_ = perception.get("self", {})
    near = perception.get("nearby_people", [])
    out: dict[str, Any] = {"thought": f"({c.title} going about the day)"}

    if hunger > 65:
        out["thought"] = "I'm famished — time to head home for a bite."
        out["action"] = {"type": "go_home"}
        out["mood"] = "hungry"
        return out

    talkable = [p for p in near if p.get("can_talk")]
    if talkable and random.random() < 0.35:
        who = random.choice(talkable)
        out["say"] = random.choice([
            f"Good day, {who['name'].split()[0]}.",
            f"Busy at the {c.workplace} today.",
            "Lovely weather for the town.",
            f"How fares the {who.get('role','work')}?",
        ])

    if directives and random.random() < 0.6:
        out["say"] = out.get("say") or "The founder's idea is on my mind — I'll do my part."
        out["action"] = {"type": "work"}
        out["goal"] = f"Help with: {directives[0][:60]}"
    elif phase == "night":
        out["action"] = {"type": "go_home"}
    else:
        r = random.random()
        if r < 0.55:
            out["action"] = {"type": "work"}
        elif r < 0.8:
            out["action"] = {"type": "move_to", "place": "Town Plaza"}
        else:
            out["action"] = {"type": "wander"}
    return out
