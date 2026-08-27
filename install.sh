#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js 18+ is required" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 1; }
(cd "$ROOT/mobile" && npm ci --ignore-scripts)
(cd "$ROOT" && ./test.sh)
echo "DataForge dependencies and tests verified"

# Desktop control-panel dependency. Kept in the project venv.
GUI_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
GUI_VENV="$GUI_ROOT/.venv"
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
[ -x "$GUI_VENV/bin/python" ] || python3 -m venv "$GUI_VENV"
"$GUI_VENV/bin/python" -m pip install --disable-pip-version-check --upgrade PySide6
touch "$GUI_VENV/.repo-gui-ready"
