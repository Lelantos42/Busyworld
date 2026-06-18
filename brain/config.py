"""Loads the shared cast (citizens.json) and per-citizen Ollama endpoints (agents.yaml)."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CITIZENS_JSON = os.path.join(ROOT, "godot", "data", "citizens.json")
AGENTS_YAML = os.path.join(HERE, "agents.yaml")


@dataclass
class Citizen:
    id: str
    name: str
    title: str
    role: str
    personality: str
    goals: list[str]
    workplace: str
    home: str
    # ollama endpoint
    host: str = "127.0.0.1"
    port: int = 11434
    model: str = "llama3.2:3b"
    model_vision: str = ""
    vision: bool = False
    temperature: float = 0.8
    timeout: int = 30

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def load_citizens() -> dict[str, Citizen]:
    with open(CITIZENS_JSON, "r", encoding="utf-8") as fh:
        cast = json.load(fh).get("citizens", [])

    endpoints: dict[str, Any] = {}
    defaults: dict[str, Any] = {}
    if os.path.exists(AGENTS_YAML):
        with open(AGENTS_YAML, "r", encoding="utf-8") as fh:
            y = yaml.safe_load(fh) or {}
        defaults = y.get("defaults", {}) or {}
        endpoints = y.get("agents", {}) or {}

    out: dict[str, Citizen] = {}
    for c in cast:
        cid = c["id"]
        ep = dict(defaults)
        ep.update(endpoints.get(cid, {}) or {})
        out[cid] = Citizen(
            id=cid,
            name=c.get("name", cid),
            title=c.get("title", ""),
            role=c.get("role", ""),
            personality=c.get("personality", ""),
            goals=c.get("goals", []),
            workplace=c.get("workplace", ""),
            home=c.get("home", ""),
            host=ep.get("host", "127.0.0.1"),
            port=int(ep.get("port", 11434)),
            model=ep.get("model", "llama3.2:3b"),
            model_vision=ep.get("model_vision", ""),
            vision=bool(ep.get("vision", False)),
            temperature=float(ep.get("temperature", 0.8)),
            timeout=int(ep.get("timeout", 30)),
        )
    return out
