#!/usr/bin/env bash
# Populate apps/sandglass/runtime/darwin-*/bin with engine binaries for bundling.
# This does NOT vendor the Lima VM image yet (first colima start still downloads it);
# shipping the image is a later packaging step.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  TRIPLET="darwin-arm64"
else
  TRIPLET="darwin-amd64"
fi

DEST="$ROOT/apps/sandglass/runtime/$TRIPLET/bin"
mkdir -p "$DEST"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing on PATH: $1 — install with: brew install colima docker eclipse-enclave" >&2
    exit 1
  fi
}

need colima
need docker
need enclave

cp "$(command -v colima)" "$DEST/colima"
cp "$(command -v docker)" "$DEST/docker"
cp "$(command -v enclave)" "$DEST/enclave"
chmod +x "$DEST"/*

# Optional helpers if present
for extra in limactl qemu-img; do
  if command -v "$extra" >/dev/null 2>&1; then
    cp "$(command -v "$extra")" "$DEST/$extra"
    chmod +x "$DEST/$extra"
  fi
done

echo "Bundled runtime binaries -> $DEST"
ls -la "$DEST"
echo
echo "Next (dev desktop):"
echo "  cd apps/sandglass && python run_desktop.py"
echo
echo "Note: Lima VM image is still pulled on first 'colima start'."
echo "Product builds should vendor ~/.colima / lima cache into the .app later."
