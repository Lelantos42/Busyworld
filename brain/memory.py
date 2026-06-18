"""Per-citizen persistence: long-term memory, journal, relationships, coins.

This is what lets a citizen live indefinitely, independent of any model's context
window. Everything a mind needs to resume its life is here in one SQLite file.
"""
from __future__ import annotations
import os
import sqlite3
import threading
import time
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")


class Memory:
    def __init__(self, world: str = "busyworld"):
        os.makedirs(STATE_DIR, exist_ok=True)
        self.path = os.path.join(STATE_DIR, f"{world}.sqlite")
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        with self._lock:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY, name TEXT, role TEXT,
                    coins INTEGER DEFAULT 100, goal TEXT DEFAULT '',
                    mood TEXT DEFAULT 'content', born REAL, last_seen REAL,
                    decisions INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT, ts REAL, kind TEXT, text TEXT,
                    importance INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS relationships (
                    agent_id TEXT, other TEXT, sentiment INTEGER DEFAULT 0,
                    note TEXT, PRIMARY KEY (agent_id, other)
                );
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT, ts REAL, delta INTEGER, reason TEXT
                );
                CREATE TABLE IF NOT EXISTS directives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL, text TEXT, status TEXT DEFAULT 'open'
                );
                CREATE TABLE IF NOT EXISTS enterprises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, kind TEXT, owner TEXT, status TEXT DEFAULT 'proposed',
                    revenue INTEGER DEFAULT 0, config TEXT, born REAL
                );
                CREATE TABLE IF NOT EXISTS world (
                    key TEXT PRIMARY KEY, value TEXT
                );
                """
            )
            # migration: add the hunger need to existing worlds
            try:
                self._db.execute("ALTER TABLE agents ADD COLUMN hunger REAL DEFAULT 20")
            except sqlite3.OperationalError:
                pass
            self._db.commit()

    # ---- agents ----------------------------------------------------------
    def ensure_agent(self, cid: str, name: str, role: str, goal: str) -> sqlite3.Row:
        with self._lock:
            row = self._db.execute("SELECT * FROM agents WHERE id=?", (cid,)).fetchone()
            if row is None:
                now = time.time()
                self._db.execute(
                    "INSERT INTO agents (id,name,role,coins,goal,born,last_seen) VALUES (?,?,?,?,?,?,?)",
                    (cid, name, role, 100, goal, now, now),
                )
                self._db.commit()
                row = self._db.execute("SELECT * FROM agents WHERE id=?", (cid,)).fetchone()
            return row

    def update_agent(self, cid: str, *, goal: str | None = None, mood: str | None = None) -> None:
        with self._lock:
            if goal is not None:
                self._db.execute("UPDATE agents SET goal=? WHERE id=?", (goal, cid))
            if mood is not None:
                self._db.execute("UPDATE agents SET mood=? WHERE id=?", (mood, cid))
            self._db.execute("UPDATE agents SET last_seen=?, decisions=decisions+1 WHERE id=?",
                             (time.time(), cid))
            self._db.commit()

    def agent(self, cid: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM agents WHERE id=?", (cid,)).fetchone()
            return dict(row) if row else {}

    # ---- memories --------------------------------------------------------
    def remember(self, cid: str, text: str, kind: str = "event", importance: int = 1) -> None:
        if not text:
            return
        with self._lock:
            self._db.execute(
                "INSERT INTO memories (agent_id,ts,kind,text,importance) VALUES (?,?,?,?,?)",
                (cid, time.time(), kind, text.strip(), importance),
            )
            self._db.commit()

    def recent_memories(self, cid: str, n: int = 8) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT text FROM memories WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                (cid, n),
            ).fetchall()
        return [r["text"] for r in reversed(rows)]

    def important_facts(self, cid: str, n: int = 6) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT text FROM memories WHERE agent_id=? AND kind='fact' "
                "ORDER BY importance DESC, id DESC LIMIT ?",
                (cid, n),
            ).fetchall()
        return [r["text"] for r in rows]

    # ---- coins / incentives ---------------------------------------------
    def add_coins(self, cid: str, delta: int, reason: str) -> int:
        with self._lock:
            self._db.execute("UPDATE agents SET coins = coins + ? WHERE id=?", (delta, cid))
            self._db.execute(
                "INSERT INTO ledger (agent_id,ts,delta,reason) VALUES (?,?,?,?)",
                (cid, time.time(), delta, reason),
            )
            self._db.commit()
            row = self._db.execute("SELECT coins FROM agents WHERE id=?", (cid,)).fetchone()
            return int(row["coins"]) if row else 0

    def treasury(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT value FROM world WHERE key='treasury'").fetchone()
            return int(row["value"]) if row else 500

    def set_treasury(self, amount: int) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO world (key,value) VALUES ('treasury',?) "
                "ON CONFLICT(key) DO UPDATE SET value=?",
                (str(amount), str(amount)),
            )
            self._db.commit()

    # ---- needs: hunger & the town food stock ----------------------------
    def hunger(self, cid: str) -> float:
        with self._lock:
            row = self._db.execute("SELECT hunger FROM agents WHERE id=?", (cid,)).fetchone()
            return float(row["hunger"]) if row and row["hunger"] is not None else 20.0

    def set_hunger(self, cid: str, value: float) -> None:
        with self._lock:
            self._db.execute("UPDATE agents SET hunger=? WHERE id=?",
                             (max(0.0, min(100.0, value)), cid))
            self._db.commit()

    def food(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT value FROM world WHERE key='food'").fetchone()
            return int(row["value"]) if row else 12

    def add_food(self, delta: int) -> int:
        with self._lock:
            new = max(0, self.food() + delta)
            self._db.execute(
                "INSERT INTO world (key,value) VALUES ('food',?) "
                "ON CONFLICT(key) DO UPDATE SET value=?", (str(new), str(new)))
            self._db.commit()
            return new

    # ---- relationships ---------------------------------------------------
    def adjust_relationship(self, cid: str, other: str, delta: int, note: str = "") -> None:
        if cid == other or not other:
            return
        with self._lock:
            row = self._db.execute(
                "SELECT sentiment FROM relationships WHERE agent_id=? AND other=?",
                (cid, other)).fetchone()
            sent = (int(row["sentiment"]) if row else 0) + delta
            sent = max(-100, min(100, sent))
            self._db.execute(
                "INSERT INTO relationships (agent_id,other,sentiment,note) VALUES (?,?,?,?) "
                "ON CONFLICT(agent_id,other) DO UPDATE SET sentiment=?, note=?",
                (cid, other, sent, note, sent, note))
            self._db.commit()

    def friends(self, cid: str, n: int = 4) -> list[tuple[str, int]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT other, sentiment FROM relationships WHERE agent_id=? "
                "ORDER BY sentiment DESC LIMIT ?", (cid, n)).fetchall()
        return [(r["other"], int(r["sentiment"])) for r in rows]

    # ---- directives & enterprises ---------------------------------------
    def add_directive(self, text: str) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO directives (ts,text) VALUES (?,?)", (time.time(), text)
            )
            self._db.commit()
            return cur.lastrowid

    def open_directives(self, n: int = 4) -> list[str]:
        with self._lock:
            rows = self._db.execute(
                "SELECT text FROM directives WHERE status='open' ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [r["text"] for r in rows]

    def add_enterprise(self, name: str, kind: str, owner: str, config: str = "") -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO enterprises (name,kind,owner,config,born) VALUES (?,?,?,?,?)",
                (name, kind, owner, config, time.time()),
            )
            self._db.commit()
            return cur.lastrowid

    def enterprises(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM enterprises").fetchall()
        return [dict(r) for r in rows]
