"""Minimal async Ollama client. Talks to each citizen's own endpoint.

Supports text chat and multimodal (image) chat. Designed to fail softly: if an
endpoint is unreachable or slow, it raises and the caller falls back to the
built-in heuristic mind, so the town never freezes.
"""
from __future__ import annotations
import json
from typing import Any

import aiohttp


class OllamaError(Exception):
    pass


async def chat(
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.8,
    timeout: int = 30,
    images: list[str] | None = None,
    json_mode: bool = True,
) -> str:
    """Return the assistant's reply text. `images` are base64 PNGs attached to the
    last user message (for vision models)."""
    msgs = [dict(m) for m in messages]
    if images:
        msgs[-1] = dict(msgs[-1])
        msgs[-1]["images"] = images
    payload: dict[str, Any] = {
        "model": model,
        "messages": msgs,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"
    url = base_url.rstrip("/") + "/api/chat"
    try:
        to = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=to) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise OllamaError(f"{url} -> HTTP {resp.status}")
                data = await resp.json()
    except aiohttp.ClientError as e:
        raise OllamaError(f"{url} unreachable: {e}") from e
    except json.JSONDecodeError as e:
        raise OllamaError(f"{url} bad json: {e}") from e
    msg = (data or {}).get("message", {})
    content = msg.get("content", "")
    if not content:
        raise OllamaError(f"{url} empty reply")
    return content


async def is_up(base_url: str, timeout: int = 3) -> bool:
    try:
        to = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=to) as session:
            async with session.get(base_url.rstrip("/") + "/api/tags") as resp:
                return resp.status == 200
    except Exception:
        return False
