#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BUILD_VENV=".venv-build"
RELEASE_DIR="release"
DATE_TAG="$(date +%Y%m%d)"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN is not available. Install Python 3.10+ and retry."
  exit 1
fi

echo "[1/5] Creating build virtual environment"
"$PYTHON_BIN" -m venv "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"

echo "[2/5] Installing dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo "[3/5] Building app with PyInstaller"
rm -rf build dist
pyinstaller --noconfirm --clean ASETMarker.spec

echo "[4/5] Preparing release bundle"
mkdir -p "$RELEASE_DIR"
MAC_ZIP="$RELEASE_DIR/ASETMarker-macOS-$DATE_TAG.zip"
rm -f "$MAC_ZIP"
ditto -c -k --sequesterRsrc --keepParent dist "$MAC_ZIP"

echo "[5/5] Done"
echo "Build output: $ROOT_DIR/dist"
echo "Client handover zip: $ROOT_DIR/$MAC_ZIP"
