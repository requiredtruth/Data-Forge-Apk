#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/desktop"
exec python3 dataforge.py
