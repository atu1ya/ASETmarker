# Everest Tutoring — ASET Marking System
Comprehensive milestone plan (M0–M8) with goals, tasks, deliverables, dependencies, inputs/outputs, acceptance criteria, and estimates.

This document recaps the full project roadmap for building a web-based ASET marking system using the existing OMR engine, adding a staff-facing web app that accepts PNG uploads and produces annotated PDFs, branded reports, and JSON results.

---

## Project Summary

- Purpose: Internal tool for Everest Tutoring staff to mark ASET practice exams quickly and consistently.
- Core features:
  - Session-based configuration: upload Reading answer key, QR/AR answer key, concept mapping JSON.
  - Single student mode: upload Reading PNG + QR/AR PNG, enter name + writing score, download a ZIP containing marked PDFs + report + JSON results.
  - Batch mode: upload manifest JSON + ZIP of student PNGs; receive per-student folder outputs in a ZIP.
  - Strengths/weaknesses: ≥51% per learning area → “Done well”; otherwise → “Needs improvement”.
- Constraints:
  - PNG-only inputs (no PDF ingestion).
  - In-memory processing; no database; do not store files after marking.
  - Staff-only (password login).
  - Hosting budget ~ $5/month.

- Current foundation:
  - Existing OMR engine in `src/*` (OMRChecker-based): template-driven bubble detection and evaluation logic.
  - We will wrap `src/*` from the web layer in `web/*` without modifying `src/*`.

---

## Milestone Overview

- M0: Project Setup & Foundation
- M1a: Template Measurement & Creation
- M1b: Template Testing & Validation
- M2: Core Marking Service Wrapper
- M3: PDF Report Generation & Annotated Sheets
- M4: Web Backend Integration
- M5: Web Frontend Completion
- M6: Batch Processing Robustness
- M7: Testing & Quality Assurance
- M8: Deployment & Documentation

Each milestone includes goals, tasks, deliverables, dependencies, inputs/outputs, acceptance criteria, and estimates.

---

## M0 — Project Setup & Foundation

### Goal
Create the web application scaffolding with authentication, session management, configuration upload, core pages, and stub services.

### Tasks
- FastAPI application setup with:
  - `web/app.py` (FastAPI init, static files, templates, health endpoint, error handlers).
  - `web/auth.py` (password-only login, HTTP-only session cookie).
  - `web/session_store.py` (in-memory per-session configuration storage).
  - `web/dependencies.py` (common dependencies for routes).
- Routes:
  - `web/routes/auth.py`: login/logout.
  - `web/routes/dashboard.py`: configuration upload (answer keys + concept mapping), status display.
  - `web/routes/marking.py`: single student workflow endpoint (stub integration).
  - `web/routes/batch.py`: batch workflow endpoint (stub integration).
- Frontend:
  - Templates (login, dashboard, single, batch) in `web/templates/*`.
  - CSS and JS in `web/static/*`.
- Services (stubs to be replaced later):
  - `web/services/marker.py`, `analysis.py`, `report.py`, `annotator.py`.
- Dev tooling:
  - Scripts (`scripts/run_dev.py`, `scripts/setup_env.py`).
  - Sample docs (answer keys, concept mapping) under `docs/`.
  - Basic tests under `tests/`.

### Deliverables
- Running dev server with:
  - Login page.
  - Dashboard to upload session configuration (reading key, qrar key, concept mapping).
  - Pages for single and batch marking (front-end forms; backend stubs return minimal responses).
- Project structure in place for subsequent milestones.

### Dependencies
- Python 3.10+
- FastAPI, Jinja2, python-multipart, OpenCV (already used in `src/*`).
- No DB.

### Inputs/Outputs
- Inputs:
  - Session config: answer keys (TXT/CSV), concept mapping (JSON).
- Outputs:
  - None final (stubs); endpoints return basic JSON or minimal PDFs.

### Acceptance Criteria
- Staff can log in.
- Staff can upload configuration per session.
- UI pages render correctly.
- Health endpoint returns “healthy”.
- No permanent data storage.

### Estimate
- 1 day.

---

## M1a — Template Measurement & Creation

### Goal
Create accurate ASET templates (JSON) for Reading and QR/AR bubble sheets from scanned PNGs.

### Tasks
- Obtain from client:
  - Blank Reading and QR/AR answer sheets.
  - Filled sample sheets + answer keys.
- Scan to PNG:
  - 300 DPI, grayscale preferred.
- Measure bubble layout using an interactive script:
  - Record `origin` (top-left of first bubble), `bubbleDimensions` (width, height), `bubblesGap` (horizontal spacing), `labelsGap` (vertical spacing).
- Create `config/aset_reading_template.json` and `config/aset_qrar_template.json`.

### Deliverables
- Two validated template JSON files:
  - `config/aset_reading_template.json`
  - `config/aset_qrar_template.json`

### Dependencies
- Scanned PNGs of ASET sheets.
- Measurement tool (OpenCV script).

### Inputs/Outputs
- Input: scanned blank sheets.
- Output: template JSONs.

### Acceptance Criteria
- Templates include correct `pageDimensions`, `bubbleDimensions`, `origin`, gaps, `fieldBlocks`, and `outputColumns` consistent with ASET layouts.

### Estimate
- 1–2 days.

---

## M1b — Template Testing & Validation

### Goal
Verify template overlays visually and functionally; refine parameters until detection is accurate.

### Tasks
- Visual alignment using `main.py --setLayout` on test directories with `template.json`.
- Functional marking test using filled samples:
  - Create `evaluation.json` with `questions_in_order` and `answers_in_order`.
  - Run `main.py -i` and validate `outputs/*`.
- Iterate `origin`, `bubblesGap`, `labelsGap`, `bubbleDimensions` until overlays align and detection matches expected answers.

### Deliverables
- Finalized and backed-up templates (reading + qrar).
- Optional: `docs/TEMPLATE_CONFIGURATION.md` summarizing measured parameters.

### Dependencies
- CLI and `src/*` OMR engine.
- Filled sample sheets.

### Inputs/Outputs
- Inputs: test images and evaluation files.
- Outputs: overlay visuals and detection results.

### Acceptance Criteria
- Overlays align across the entire sheet regions.
- Functional tests detect correct answers with ≥95% accuracy on good scans.

### Estimate
- 0.5–1 day.

---

## M2 — Core Marking Service Wrapper

### Goal
Implement production-grade services that wrap the OMR engine (`src/*`) to process PNGs, detect responses, and compute scores.

### Tasks
- Implement `web/services/marker.py`:
  - Load `Template` from `config/aset_reading_template.json` and `config/aset_qrar_template.json`.
  - Convert uploaded image bytes → CV2 grayscale image.
  - Apply preprocessors and read OMR responses via `template.image_instance_ops`.
  - Use `get_concatenated_response` to map detected bubbles to question labels.
  - Evaluate against uploaded answer keys; build dataclasses:
    - `QuestionResult`, `SubjectResult`, `MarkingResult`, `QRARMarkingResult`.
  - Error handling (invalid PNG, missing template, preprocessing failure).
- Implement `web/services/analysis.py`:
  - Clean/validate concept mapping.
  - Compute per-area percentages; apply 51% threshold.
  - Return dataclasses:
    - `LearningAreaResult`, `SubjectAnalysis`, `FullAnalysis`.
- Update `web/services/__init__.py` exports.

### Deliverables
- Fully implemented `marker.py` and `analysis.py` with typed dataclasses, ready for route integration.

### Dependencies
- `src/template.Template`, `src/core.ImageInstanceOps`, `src.defaults.CONFIG_DEFAULTS`, `src.utils.parsing.get_concatenated_response`.
- Finalized template JSONs from M1a/b.

### Inputs/Outputs
- Inputs: PNG bytes, answer keys, concept mapping.
- Outputs: structured results (SubjectResult), marked image arrays, raw response dicts.

### Acceptance Criteria
- Services return accurate results and handle errors gracefully.
- No modification of `src/*`; wrappers only.

### Estimate
- 1–2 days.

---

## M3 — PDF Report Generation & Annotated Sheets

### Goal
Produce branded student report PDF and annotated marked sheet PDFs.

### Tasks
- Implement `web/services/report.py`:
  - Use ReportLab (preferred) to generate branded report:
    - Title, logo (if available), student name, writing score, Reading/QR/AR scores.
    - Strengths/improvements sections using `FullAnalysis`.
    - Professional layout (colors: #3498DB, #2C3E50).
- Implement `web/services/annotator.py`:
  - Overlay detection summary (score text; optional bubble highlights if coordinates available).
  - Convert marked CV2 image to PDF bytes (via PIL or ReportLab).
- Ensure functions return PDF bytes suitable for ZIP bundling.

### Deliverables
- `generate_student_report(...) -> bytes`.
- `annotate_sheet(...) -> np.ndarray` and `image_to_pdf_bytes(...) -> bytes`.

### Dependencies
- Subject and analysis results from M2.

### Inputs/Outputs
- Inputs: `SubjectResult`, `FullAnalysis`, CV2 images.
- Outputs: PDF bytes for report and annotated sheets.

### Acceptance Criteria
- PDFs are branded, readable, and match the business format.
- Annotated PDFs clearly indicate incorrect answers or include summary annotations.

### Estimate
- 1–2 days.

---

## M4 — Web Backend Integration

### Goal
Wire the real services into single and batch routes; return final ZIPs.

### Tasks
- Update `web/routes/marking.py`:
  - Validate session configuration exists (reading key, qrar key, concept mapping).
  - Process uploaded `reading_sheet` and `qrar_sheet` PNGs via `MarkingService`.
  - Compute `FullAnalysis` via `AnalysisService`.
  - Generate PDFs via `AnnotatorService` and `ReportService`.
  - Prepare `results.json`.
  - Package into a single ZIP (in-memory) and stream back.
- Update `web/routes/batch.py`:
  - Parse manifest JSON; extract files from ZIP.
  - Process each student; build per-student folders in output ZIP (in-memory).
  - Stream final ZIP.

### Deliverables
- Functional endpoints:
  - `POST /mark/single/process` → single student ZIP.
  - `POST /batch/process` → batch ZIP with per-student folders.

### Dependencies
- M2 and M3 services; session config from dashboard.

### Inputs/Outputs
- Inputs: PNGs, student info, manifest JSON.
- Outputs: ZIP streams containing PDFs and JSON.

### Acceptance Criteria
- Endpoints return correct ZIPs.
- Errors handled with clear messages (HTTP 4xx for user errors).

### Estimate
- 2 days.

---

## M5 — Web Frontend Completion

### Goal
Polish the UI and UX for staff workflows.

### Tasks
- Dashboard:
  - Show configuration status (counts of questions, subjects mapped).
  - Enable mode cards only after config load.
- Single page:
  - File previews, async submission, spinner.
  - Success messaging, “Mark another student”.
- Batch page:
  - Manifest instructions; sample download; async submission; spinner.
- CSS/JS refinements (responsive design).

### Deliverables
- Professional, responsive UI aligned to business needs.

### Dependencies
- M4 routes.

### Inputs/Outputs
- Inputs: staff interactions and uploads.
- Outputs: same as M4; UI improvements.

### Acceptance Criteria
- Clear guidance for staff; minimal friction; reliable feedback and downloads.

### Estimate
- 1–2 days.

---

## M6 — Batch Processing Robustness

### Goal
Harden batch workflow and output organization.

### Tasks
- Manifest validation (types, required fields).
- Graceful handling of missing files; partial results with reporting.
- Consistent folder naming in output ZIP (`First_Last/`).
- Optional summary CSV or JSON at ZIP root (aggregate results).

### Deliverables
- Stable batch processing with robust manifest handling and clean outputs.

### Dependencies
- M4, M5.

### Inputs/Outputs
- Inputs: manifest JSON, ZIP of PNGs.
- Outputs: foldered ZIP; optional summary.

### Acceptance Criteria
- Batch runs reliably across realistic workloads; helpful error messages if inputs are invalid.

### Estimate
- 1 day.

---

## M7 — Testing & Quality Assurance

### Goal
Achieve confidence via unit, integration, and end-to-end tests; cover edge cases.

### Tasks
- Unit tests:
  - `test_marker_service.py`: template loading, PNG validation, response evaluation, error paths.
  - `test_analysis_service.py`: concept mapping validation, per-area calculation, threshold boundaries (50%, 51%, 52%).
- Integration tests:
  - Routes (auth, configuration upload, single/batch).
  - Small PNGs; mock where needed.
- Manual UAT:
  - With real ASET PNGs; confirm accuracy; verify annotated/report PDFs.

### Deliverables
- Test suite passing; documentation of known limitations and edge cases.

### Dependencies
- All prior milestones.

### Inputs/Outputs
- Inputs: sample PNGs, configs.
- Outputs: test reports.

### Acceptance Criteria
- Meaningful test coverage; stable end-to-end flows; acceptable accuracy on client samples.

### Estimate
- 1–2 days.

---

## M8 — Deployment & Documentation

### Goal
Package for hosting and handover to staff.

### Tasks
- Dockerfile with OpenCV runtime libs.
- Deploy to Railway/Render/Fly.io; set env vars:
  - `STAFF_PASSWORD`, `SECRET_KEY`, optionally `DEBUG`.
- Staff documentation:
  - Login, configuration upload, single/batch steps, troubleshooting.
- Handover package:
  - Source access (if agreed), credentials, ongoing support notes.

### Deliverables
- Hosted application accessible to staff; documentation ready; handover completed.

### Dependencies
- All prior milestones.

### Inputs/Outputs
- Inputs: hosting platform configs.
- Outputs: live app, docs.

### Acceptance Criteria
- Staff can use the system without technical assistance; meets privacy/storage constraints; reliable ZIP outputs.

### Estimate
- 1 day.

---

## Cross-Milestone Guardrails

- Do not modify `src/*` unless absolutely necessary; prefer wrapper services in `web/services/*`.
- PNG-only acceptance; reject other formats.
- Session-based configuration; no permanent storage; return outputs immediately and do not retain files.
- Implement robust error handling and user-friendly messages.
- Use typed dataclasses and Python type hints throughout.
- Outputs: For single student:
  - `<student>_reading_marked.pdf`
  - `<student>_qrar_marked.pdf`
  - `<student>_report.pdf`
  - `<student>_results.json`
  - → packaged into a ZIP and streamed back.
- Batch: Per-student folder with the same files; optional summary at root.

---

## Timeline Summary

| Milestone | Estimate |
|-----------|----------|
| M0 | 1 day |
| M1a | 1–2 days |
| M1b | 0.5–1 day |
| M2 | 1–2 days |
| M3 | 1–2 days |
| M4 | 2 days |
| M5 | 1–2 days |
| M6 | 1 day |
| M7 | 1–2 days |
| M8 | 1 day |

Total: ~10–15 days depending on iteration and testing depth.

---

## Inputs & Artifacts Checklist

- From client:
  - Blank Reading / QR/AR sheets (PNG scans).
  - Filled samples + answer keys.
- Created:
  - `config/aset_reading_template.json`
  - `config/aset_qrar_template.json`
  - Concept mapping JSON (staff uploads per session).
- Outputs per student:
  - Annotated PDFs (Reading, QR/AR)
  - Branded report PDF
  - JSON results
  - ZIP packaging (single or batch).

---

## Acceptance Criteria (Global)

- Staff can log in, upload session configuration, and run single and batch marking.
- Bubble detection is reliable for ASET sheets per finalized templates.
- Annotated PDFs clearly indicate incorrect items or provide clear summary annotations.
- Branded report PDF adheres to business formatting; includes strengths/improvements using the 51% threshold.
- No personal data retained beyond immediate response; no database usage.
- App is deployable and documented; staff can operate without technical support.

---

## Notes to Developers/LLMs

- Reference and wrap `src/*`:
  - `src/template.Template`
  - `src/core.ImageInstanceOps`
  - `src.defaults.CONFIG_DEFAULTS`
  - `src.utils.parsing.get_concatenated_response`
- Provide code using typed dataclasses and explicit error handling.
- When proposing code in downstream conversations, use file blocks indicating exact paths.
- Be explicit about PNG validation and session-only configuration.

---