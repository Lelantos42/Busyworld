#!/usr/bin/env python3
"""Busyworld brain server.

A lightweight WebSocket middleware between the Godot town (authoritative for
space + time) and the citizens' local Ollama minds (authoritative for thought +
memory + economy). Run it, then launch the game; the town will start thinking.

    python3 brain/server.py --world busyworld --host 127.0.0.1 --port 8765

Citizens whose models are unreachable fall back to a heuristic mind, so the town
lives even with no models running.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import re
from typing import Any

import websockets

from config import load_citizens
from memory import Memory
import mind

CITIZENS = load_citizens()
MEM: Memory
ACTIVE: set[str] = set()


async def send(ws, msg: dict[str, Any]) -> None:
    try:
        await ws.send(json.dumps(msg))
    except Exception:
        pass


async def handle_decide(ws, msg: dict[str, Any]) -> None:
    cid = str(msg.get("agent_id", ""))
    c = CITIZENS.get(cid)
    if c is None:
        return
    perception = msg.get("perception", {})
    image = msg.get("image")
    directives = MEM.open_directives()
    try:
        results = await mind.decide(c, perception, MEM, directives, image)
    except Exception as e:  # never let one mind crash the town
        print(f"[decide:{cid}] error: {e}")
        return
    model_used = False
    for r in results:
        if "used_model" in r:
            model_used = r["used_model"]
            continue
        await send(ws, r)
    tag = "model" if model_used else "instinct"
    say = next((r.get("say") for r in results if r.get("say")), "")
    print(f"[{cid:10s}] {tag:8s} {results[0]['action'].get('type','?'):8s} {say}")


ENTERPRISE_HINTS = {
    "store": "shop", "shop": "shop", "bakery": "bakery", "market": "market",
    "stall": "stall", "business": "business", "cafe": "cafe", "farm": "farm",
}


def _parse_amount(text: str, default: int) -> int:
    import re
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else default


async def handle_player_request(ws, msg: dict[str, Any]) -> None:
    text = str(msg.get("text", "")).strip()
    if not text:
        return
    low = text.lower()

    # the founder provides for the town: food and virtual money
    if "food" in low or "meal" in low or "feed" in low:
        amt = _parse_amount(text, 20)
        total = MEM.add_food(amt)
        await send(ws, {"type": "announce",
                        "text": f"[founder] restocked the larder with {amt} meals ({total} in store)."})
        return
    if any(w in low for w in ("coin", "money", "pay", "reward", "wage")):
        amt = _parse_amount(text, 50)
        for cid in (ACTIVE or set(CITIZENS)):
            MEM.add_coins(cid, amt, "a gift from the founder")
        MEM.set_treasury(MEM.treasury() + amt * max(1, len(ACTIVE)))
        await send(ws, {"type": "announce",
                        "text": f"[founder] granted {amt} coins to every citizen."})
        await send(ws, {"type": "treasury", "amount": MEM.treasury()})
        if "mayor" in CITIZENS:
            await send(ws, {"type": "say", "agent_id": "mayor",
                            "text": f"The founder has blessed us with {amt} coins each. Generous!"})
        return

    MEM.add_directive(text)
    print(f"[founder] {text}")
    # detect a possible enterprise and record it (scaffold for real ventures)
    kind = next((v for k, v in ENTERPRISE_HINTS.items() if k in text.lower()), "")
    if kind:
        owner = "shopkeeper" if "shopkeeper" in CITIZENS else next(iter(CITIZENS))
        eid = MEM.add_enterprise(name=text[:48], kind=kind, owner=owner, config=text)
        await send(ws, {"type": "log",
                        "text": f"[enterprise #{eid}] a new {kind} venture is on the books."})
    # the mayor acknowledges to the town
    if "mayor" in CITIZENS:
        await send(ws, {"type": "say", "agent_id": "mayor",
                        "text": f"The founder asks us to {text}. Let's make it happen!"})
    await send(ws, {"type": "announce",
                    "text": f"[town directive] {text}"})


async def handler(ws) -> None:
    print("[brain] game client connected")
    await send(ws, {"type": "log", "text": "[brain] connected — minds online."})
    await send(ws, {"type": "treasury", "amount": MEM.treasury()})
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = str(msg.get("type", ""))
            if mtype == "hello":
                ACTIVE.clear()
                ACTIVE.update(msg.get("active", []))
                print(f"[brain] active citizens: {sorted(ACTIVE)}")
                vids = [cid for cid in ACTIVE if CITIZENS.get(cid) and CITIZENS[cid].vision]
                await send(ws, {"type": "vision", "ids": vids})
            elif mtype == "decide":
                asyncio.create_task(handle_decide(ws, msg))
            elif mtype == "player_request":
                asyncio.create_task(handle_player_request(ws, msg))
    except websockets.ConnectionClosed:
        pass
    finally:
        print("[brain] game client disconnected")


async def main() -> None:
    global MEM
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="busyworld")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    MEM = Memory(args.world)
    print(f"[brain] world='{args.world}'  citizens={len(CITIZENS)}  "
          f"treasury={MEM.treasury()}  listening on ws://{args.host}:{args.port}")
    for c in CITIZENS.values():
        MEM.ensure_agent(c.id, c.name, c.role, c.goals[0] if c.goals else "")

    async with websockets.serve(handler, args.host, args.port, ping_interval=20):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[brain] shutting down.")
