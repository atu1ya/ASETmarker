# ASET Marker (Desktop)

ASET Marker is now a desktop-first marking tool. It runs locally, processes merged exam documents, and generates per-student marked images plus DOCX reports.

## What It Does

- Marks Reading + QR/AR from a single merged exam document.
- Supports two workflows:
  - Single Student: one merged file + student details.
  - Batch Processing: folder of merged files + roster spreadsheet (CSV/Excel).
- Splits merged documents in strict page order:
  - Page 1: Reading
  - Page 2: QR/AR
  - Page 3: Writing
- Generates organized outputs per student:
  - reading_marked.png
  - qrar_marked.png (QR on top, AR on bottom)
  - writing_page.png
  - report.docx
  - analysis.json

## Project Layout

- main_gui.py: Desktop GUI entrypoint.
- desktop/pipeline.py: Batch/single orchestration.
- desktop/io/merged_document_splitter.py: Merged document page extraction.
- desktop/services/: Marking, annotation, analysis, DOCX report logic.
- config/: OMR templates and concept configs.
- docs/: answer keys and supporting data.
- build/: PyInstaller spec files.
- scripts/: local build helpers.

## Requirements

- Python 3.10+
- Windows or macOS

## Local Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

## Run Desktop App

```bash
python main_gui.py
```

## Workflow Details

### Single Student

1. Choose one merged document (.pdf/.tif/.tiff/.png/.jpg/.jpeg).
2. Enter student name and writing score.
3. Start marking.

### Batch Processing

1. Choose exam folder (or single file when testing).
2. Choose roster file (.csv/.xlsx/.xls) with columns:
   - Student Name
   - Writing Score
3. Ensure scan filenames map to student names.
4. Start marking.

## Build Executables

### Windows (.exe)

```powershell
./scripts/build_windows.ps1
```

### macOS

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

Build artifacts are produced in dist/.

## CI

GitHub Actions builds desktop artifacts for Windows and macOS and runs core tests from src/tests.

## Notes

- This repository no longer ships web routes, dashboards, or Docker deployment.
- Inputs must follow the strict 3-page merged order for marking to run.
