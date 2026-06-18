#!/usr/bin/env python3
"""Busyworld launcher (Linux / macOS / Windows).

Starts the brain server and the Godot town together.

    python3 launch.py                 # start with the default number of citizens
    python3 launch.py --agents 3      # start only 3 citizens
    python3 launch.py --no-brain      # just the town (citizens run on local instinct)
    python3 launch.py --brain-only    # just the brain server

Godot is located via (in order): --godot PATH, the GODOT env var, ./tools/bin/godot,
or `godot`/`godot4` on PATH. If none is found, the brain still runs and you can open
the ./godot project in the Godot editor and press Play.
"""
from __future__ import annotations
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def find_godot(explicit: str | None) -> str | None:
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("GODOT"):
        candidates.append(os.environ["GODOT"])
    candidates.append(os.path.join(ROOT, "tools", "bin", "godot"))
    for name in ("godot", "godot4", "Godot"):
        p = shutil.which(name)
        if p:
            candidates.append(p)
    for c in candidates:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
        w = shutil.which(c) if c else None
        if w:
            return w
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", type=int, default=None, help="number of citizens to start")
    ap.add_argument("--world", default="busyworld")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--godot", default=None, help="path to the Godot 4.3 binary")
    ap.add_argument("--no-brain", action="store_true", help="run the town without the brain")
    ap.add_argument("--brain-only", action="store_true", help="run only the brain server")
    args = ap.parse_args()

    procs: list[subprocess.Popen] = []
    try:
        if not args.no_brain:
            print("[launch] starting brain server…")
            procs.append(subprocess.Popen(
                [PY, os.path.join(ROOT, "brain", "server.py"),
                 "--world", args.world, "--host", args.host, "--port", str(args.port)],
                cwd=os.path.join(ROOT, "brain"),
            ))
            time.sleep(1.5)

        if not args.brain_only:
            godot = find_godot(args.godot)
            if not godot:
                print("[launch] Godot binary not found. The brain is running; open the "
                      "'godot' project in the Godot 4.3 editor and press Play.")
            else:
                game_args = [godot, "--path", os.path.join(ROOT, "godot")]
                passthrough = []
                if args.agents is not None:
                    passthrough += ["--agents", str(args.agents)]
                if passthrough:
                    game_args += ["--"] + passthrough
                print(f"[launch] starting town: {godot}")
                procs.append(subprocess.Popen(game_args, cwd=ROOT))

        if not procs:
            return 0
        # wait until any child exits, then tear the rest down
        while True:
            for p in procs:
                if p.poll() is not None:
                    raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[launch] shutting down…")
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        time.sleep(0.5)
        for p in procs:
            if p.poll() is None:
                p.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
