#!/usr/bin/env bash
# Run / screenshot the Busyworld Godot client headlessly (software GL via Xvfb).
# Usage:
#   tools/run_godot.sh import                         # import assets only
#   tools/run_godot.sh shot OUT.png [DELAY] [ARGS...] # render one screenshot then quit
#   tools/run_godot.sh series OUT.png N DELAY [ARGS]  # N screenshots, DELAY apart
#   tools/run_godot.sh play [ARGS...]                 # run windowed (under Xvfb)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="$ROOT/tools/bin/godot"
PROJ="$ROOT/godot"
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
XVFB=(xvfb-run -a -s "-screen 0 1920x1080x24")

cmd="${1:-play}"; shift || true
case "$cmd" in
  import)
    "$GODOT" --headless --path "$PROJ" --import 2>&1 | tail -25
    ;;
  shot)
    OUT="$(realpath -m "$1")"; DELAY="${2:-8}"; shift 2 || true
    "${XVFB[@]}" "$GODOT" --path "$PROJ" --resolution 1920x1080 \
      -- --autopilot --screenshot "$OUT" --shotdelay "$DELAY" --shotseries 1 "$@" 2>&1 | tail -40
    ;;
  series)
    OUT="$(realpath -m "$1")"; N="$2"; DELAY="$3"; shift 3 || true
    "${XVFB[@]}" "$GODOT" --path "$PROJ" --resolution 1920x1080 \
      -- --screenshot "$OUT" --shotseries "$N" --shotdelay "$DELAY" "$@" 2>&1 | tail -40
    ;;
  play)
    "${XVFB[@]}" "$GODOT" --path "$PROJ" --resolution 1920x1080 -- "$@" 2>&1 | tail -60
    ;;
esac
