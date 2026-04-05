#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f ./.venv/bin/python ]]; then
  echo "Virtual environment not found. Create .venv and install requirements first."
  exit 1
fi

./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m PyInstaller --noconfirm --clean build/asetmarker-macos.spec

echo "macOS build complete. Output is in dist/."
