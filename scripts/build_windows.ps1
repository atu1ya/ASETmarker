$ErrorActionPreference = "Stop"

$python = "./.venv/Scripts/python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Create .venv and install requirements first."
}

& $python -m pip install -r requirements.txt
& $python -m PyInstaller --noconfirm --clean build/asetmarker-windows.spec

Write-Host "Windows build complete. Output is in dist/."
