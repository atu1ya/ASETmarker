#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BUILD_VENV=".venv-build"
RELEASE_DIR="release"
DATE_TAG="$(date +%Y%m%d)"
ICON_SOURCE="docs/assets/colored_output.jpg"
ICONSET_DIR="build/iconset"
ICON_OUTPUT="assets/ASETMarker.icns"
HANDOVER_DIR="$RELEASE_DIR/ASETMarker-macOS-$DATE_TAG"

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

echo "[3/6] Generating app icon"
if [[ -f "$ICON_SOURCE" ]]; then
  rm -rf "$ICONSET_DIR"
  mkdir -p "$ICONSET_DIR"
  sips -z 16 16 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
  sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
  sips -z 64 64 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
  sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
  sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
  iconutil -c icns "$ICONSET_DIR" -o "$ICON_OUTPUT"
fi

echo "[4/6] Building app with PyInstaller"
rm -rf build dist
pyinstaller --noconfirm --clean ASETMarker.spec

echo "[5/6] Preparing release bundle"
mkdir -p "$RELEASE_DIR"
rm -rf "$HANDOVER_DIR"
mkdir -p "$HANDOVER_DIR"
cp -R dist/ASETMarker.app "$HANDOVER_DIR/"
if [[ -f "$ICON_SOURCE" ]]; then
  cp "$ICON_SOURCE" "$HANDOVER_DIR/Cover_Image.jpg"
fi
cat > "$HANDOVER_DIR/How_to_Run.txt" << 'EOF'
ASET Marker - macOS Client Handover

1. Move ASETMarker.app to Applications.
2. Open ASETMarker.app.
3. If blocked on first run: right-click app and select Open.
EOF

MAC_ZIP="$RELEASE_DIR/ASETMarker-macOS-$DATE_TAG.zip"
rm -f "$MAC_ZIP"
ditto -c -k --sequesterRsrc --keepParent "$HANDOVER_DIR" "$MAC_ZIP"

echo "[6/6] Done"
echo "Build output: $ROOT_DIR/dist/ASETMarker.app"
echo "Handover folder: $ROOT_DIR/$HANDOVER_DIR"
echo "Client handover zip: $ROOT_DIR/$MAC_ZIP"
