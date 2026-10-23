#!/usr/bin/env bash
# Build Sandglass.app (double-clickable). Optionally stage runtime/ first.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$ROOT/apps/sandglass"
cd "$APP_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install -q -r requirements.txt
pip install -q "pyinstaller>=6.3"

if [[ "${PREPARE_RUNTIME:-1}" == "1" ]]; then
  if command -v colima >/dev/null 2>&1 && command -v docker >/dev/null 2>&1 && command -v enclave >/dev/null 2>&1; then
    "$ROOT/scripts/prepare_runtime_macos.sh" || true
  else
    echo "WARN: colima/docker/enclave not all on PATH — building UI-only .app (engineMode=system until runtime/ is filled)"
  fi
fi

rm -rf build dist
pyinstaller --noconfirm sandglass.spec

echo
echo "Built: $APP_DIR/dist/Sandglass.app"
echo "Open with: open dist/Sandglass.app"
echo
echo "Note: first-run Colima may still download a Lima VM image unless you vendor it later."
