#!/usr/bin/env bash
# Busyworld — Linux/macOS quick start.  Usage: ./run.sh [--agents N] [extra launch.py args]
set -e
cd "$(dirname "$0")"
python3 launch.py "$@"
