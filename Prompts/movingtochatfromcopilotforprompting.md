# Everest Tutoring — ASET Marking System
Full consolidated context and implementation roadmap for continuing work with an AI LLM

This document is designed to be pasted into Gemini, ChatGPT, or another LLM to continue development. It contains:
- Project context and constraints
- Current repository structure and relevant source files
- What has been completed so far (Milestones M0, M1a, M1b)
- What remains (Milestones M2–M8), with detailed requirements and deliverables
- Exact file paths, data models, and interface specs
- Input/output formats, testing, deployment, and acceptance criteria
- Guardrails for the LLM to follow (e.g., don’t modify src/*)

---

## 1. Project Overview

- Goal: Deliver a web-based automated marking system for ASET practice exams for Everest Tutoring staff. Staff upload PNG scans of answer sheets and receive:
  - Annotated marked PDFs (Reading, QR/AR)
  - Branded student report PDF
  - JSON results file
  - All packaged in a ZIP for single student or batch processing.

- Intended users: Internal staff only (tutors, admin staff, mock exam coordinators). Not student-facing.

- Scope highlights:
  - Staff login using a pre-defined shared password.
  - Session-based marking configuration:
    - Upload Reading answer key (TXT/CSV)
    - Upload QR/AR answer key (TXT/CSV)
    - Upload concept mapping JSON (dynamic; staff adjust each session)
  - Two modes:
    - Single student: Upload Reading PNG + QR/AR PNG; enter student name + writing score; download ZIP.
    - Batch: Upload ZIP of PNG sheets + manifest JSON mapping files to students; receive batch ZIP with per-student folders.
  - Strengths/weaknesses rule: ≥51% per learning area is “Done well”; <51% is “Needs improvement”.
  - Technical constraints:
    - No database; in-memory processing per session
    - PNG-only inputs (no PDF ingestion of scans)
    - Files are not stored after marking
    - Hosting budget: ~ $5/month

---

## 2. Repository Context

- Repo: [atu1ya/ASETmarker](https://github.com/atu1ya/ASETmarker)
- Description: “Marker, finish off. Use open source marking protocol, custom report generation and marking”
- Language: Python (100%)

### 2.1 Key files and directories (selected)

- `main.py`
  - CLI entry point; parses arguments; calls `src/entry.py`.

- `src/template.py`
  - Loads and validates `template.json`.
  - Defines `Template` and `FieldBlock`.
  - `Template` sets:
    - `image_instance_ops` = `ImageInstanceOps(tuning_config)`
    - `pre_processors` from JSON
    - `field_blocks` and `bubble grid` positioning
    - `pageDimensions`, `bubbleDimensions`, `emptyValue`
    - `outputColumns`

- `src/core.py`
  - `ImageInstanceOps`: CV2-based pipeline for bubble detection & alignment:
    - `apply_preprocessors(...)`: Crop, align, normalize per template.
    - `read_omr_response(...)`: Detect bubbles, compute thresholds, return final marked overlay and response dict.

- `src/evaluation.py`
  - `EvaluationConfig`: Parses answer key (CSV or via image), validates marking schemes.
  - `AnswerMatcher`: Supports standard, multiple-correct, and weighted answers.
  - `SectionMarkingScheme`: Marking per verdict (“correct”, “incorrect”, “unmarked”). Default and custom sections supported.

- `src/entry.py`
  - Orchestrates directory recursive processing.
  - Loads config, template, and (optionally) evaluation config.
  - Applies template to images; writes outputs, stats.

- `src/utils/*`, `src/processors/*`, `src/constants/*`, `src/defaults/*`, `src/schemas/*`
  - Helpers for parsing, file I/O, image ops, UI display (debug).
  - Preprocessors include `CropPage`, `CropOnMarkers`, `FeatureBasedAlignment`.

- `requirements.txt` (project dependencies; opencv, numpy, pandas, etc.)

Important: src/* is a mature OMR system (“OMRChecker”). We will wrap it for a web workflow. Do not modify src/* unless absolutely necessary—prefer adding wrappers in web/services/*.

---

## 3. Completed Work (Milestones)

### M0 — Project Setup & Foundation
Status: Completed (Scaffolding + stubs ready)

- FastAPI app with routes for login, dashboard, marking, batch.
- Simple password-only staff authentication:
  - Session tokens via HTTP-only cookies.
  - In-memory session storage (no database).
- Dashboard workflow:
  - Staff upload Reading answer key (TXT/CSV), QR/AR answer key (TXT/CSV), concept mapping JSON.
  - Stored in session (in-memory).
- Frontend:
  - Jinja2 templates (login, dashboard, single, batch), CSS, JS.
- Services layer (stubs):
  - MarkingService (stub)
  - AnalysisService (stub)
  - ReportService (stub; minimal PDF)
  - AnnotatorService (stub; minimal PDF)
- Docs: sample answer keys and concept mapping.
- Tests scaffolding.

Project structure created (see Section 4).

### M1a — Template Measurement & Creation (Manual)
Status: Completed (by you)

- Scan blank Reading and QR/AR sheets (PNG, 300 DPI).
- Measure bubble origins, gap between bubbles, gap between rows, bubble dimensions using interactive tool.
- Create templates:
  - `config/aset_reading_template.json`
  - `config/aset_qrar_template.json`
- These templates define exact layout (origins, dimensions, gaps, labels, bubble values).

### M1b — Template Testing & Validation (Manual)
Status: Completed (by you)

- Verified overlays using `main.py --setLayout`.
- Iterated until bubble rectangles aligned with captured sheets.
- Tested marking with filled sample sheets; validated detection accuracy.

Note: Because M1a and M1b are complete and templates are available, the remaining milestones can now build the web layer that wraps src/* logic and produce outputs per the client brief.

---

## 4. Target Project Structure (from M0; for reference)

The project should now have this layout (stubs present to be implemented):

```
ASETmarker/
├── src/                          # [EXISTING - DO NOT MODIFY]
│   └── ...  (existing OMR code)
├── web/
│   ├── __init__.py
│   ├── app.py                    # FastAPI application entry point
│   ├── auth.py                   # Password-based authentication
│   ├── config.py                 # Application configuration
│   ├── dependencies.py           # FastAPI dependencies
│   ├── session_store.py          # In-memory session configuration storage
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py               # Login/logout routes
│   │   ├── dashboard.py          # Dashboard and configuration routes
│   │   ├── marking.py            # Single student marking routes
│   │   └── batch.py              # Batch processing routes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── marker.py             # OMR marking service wrapper (stub → to implement)
│   │   ├── analysis.py           # Strengths/weaknesses analysis (stub → to implement)
│   │   ├── report.py             # PDF report generation (stub → to implement)
│   │   └── annotator.py          # Annotated sheet generation (stub → to implement)
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   └── app.js
│   │   └── images/
│   │       └── .gitkeep
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── single.html
│       ├── batch.html
│       └── components/
│           ├── navbar.html
│           ├── flash.html
│           └── footer.html
├── config/
│   ├── __init__.py
│   ├── aset_reading_template.json    # [From M1a/M1b]
│   └── aset_qrar_template.json       # [From M1a/M1b]
├── assets/
│   ├── .gitkeep
│   └── fonts/
│       └── .gitkeep
├── docs/
│   ├── sample_answer_key.txt
│   ├── sample_answer_key.csv
│   └── sample_concept_mapping.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_services.py
│   └── test_routes.py
├── scripts/
│   ├── run_dev.py
│   ├── setup_env.py
│   └── measure_template.py
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements.dev.txt
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── DEVELOPMENT.md
```

---

## 5. Remaining Milestones (Detailed)

Below are the remaining milestones with precise tasks, deliverables, and guardrails. The LLM should implement these in order:

### M2 — Core Marking Service Wrapper
Goal: Replace stubs with production-grade services integrated with src/*.

Implement `web/services/marker.py`:

- Constraints:
  - Do not modify src/*.
  - Load templates from `config/aset_reading_template.json` and `config/aset_qrar_template.json`.
  - PNG-only inputs; validate and error out for non-PNG.
  - In-memory processing only; do not persist student data.
  - Provide structured dataclasses with type hints.

- Key dependencies from src/*:
  - `src.template.Template`
  - `src.core.ImageInstanceOps` via `template.image_instance_ops`
  - `src.defaults.CONFIG_DEFAULTS`
  - `src.utils.parsing.get_concatenated_response`
  - `src.logger.logger`

- Implement dataclasses:

```python
from dataclasses import dataclass
from typing import List, Optional, Dict
import numpy as np

@dataclass
class QuestionResult:
    question: str            # e.g., "q1", "qr5", "ar10"
    student_answer: str      # Detected answer or empty string
    correct_answer: str
    is_correct: bool
    is_unmarked: bool

@dataclass
class SubjectResult:
    subject: str             # "Reading", "Quantitative Reasoning", "Abstract Reasoning"
    correct: int
    incorrect: int
    unmarked: int
    total: int
    percentage: float
    questions: List[QuestionResult]

@dataclass
class MarkingResult:
    success: bool
    error_message: Optional[str]
    subject_result: Optional[SubjectResult]
    marked_image: Optional[np.ndarray]   # CV2 image for annotated sheet
    multi_marked: bool
    raw_responses: Dict[str, str]        # e.g., {"q1": "A", ... }

@dataclass
class QRARMarkingResult:
    success: bool
    error_message: Optional[str]
    qr_result: Optional[SubjectResult]
    ar_result: Optional[SubjectResult]
    marked_image: Optional[np.ndarray]
    multi_marked: bool
    raw_responses: Dict[str, str]        # e.g., {"qr1": "C", "ar1": "E", ...}
```

- Implement `MarkingService` methods:

```python
class MarkingService:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.reading_template = None
        self.qrar_template = None
    
    def _load_reading_template(self) -> None:
        # Load Template(config_dir / "aset_reading_template.json", CONFIG_DEFAULTS)
    
    def _load_qrar_template(self) -> None:
        # Load Template(config_dir / "aset_qrar_template.json", CONFIG_DEFAULTS)

    def _bytes_to_cv_image(self, image_bytes: bytes) -> np.ndarray:
        # Validate PNG magic header; convert to np.ndarray via cv2.imdecode(IMREAD_GRAYSCALE); raise error on failure
    
    def mark_reading_sheet(self, image_bytes: bytes, answer_key: List[str]) -> MarkingResult:
        # 1) Ensure template loaded
        # 2) Convert bytes to CV2 image
        # 3) Apply preprocessors via template.image_instance_ops.apply_preprocessors
        # 4) Read OMR response via template.image_instance_ops.read_omr_response
        # 5) get_concatenated_response(response_dict, template) → raw_responses
        # 6) Evaluate against answer_key → SubjectResult
        # 7) Return MarkingResult with marked image and multi_marked flag

    def mark_qrar_sheet(self, image_bytes: bytes, qr_answer_key: List[str], ar_answer_key: List[str]) -> QRARMarkingResult:
        # Similar to reading; but split concatenated response into QR and AR per template’s outputColumns.
        # Evaluate each section independently and return combined result.
```

- Evaluate responses (helper):

```python
def _evaluate_responses(detected_responses: Dict[str, str],
                        answer_key: List[str],
                        label_prefix: str,       # e.g., "q", "qr", "ar"
                        subject_name: str) -> SubjectResult:
    # For i in range(len(answer_key)):
    #   q_label = f"{label_prefix}{i+1}"
    #   student = detected_responses.get(q_label, "")
    #   correct = answer_key[i]
    #   is_unmarked = (student == "" or student == <template.emptyValue>)
    #   is_correct = (student == correct)
    # Aggregate counts; compute percentage; produce QuestionResult list.
```

Error handling:
- Missing template file → return `success=False`, `error_message`.
- Invalid image bytes or not PNG → return `success=False`, `error_message`.
- Preprocessor failure (returns None) → return `success=False`.
- No markers detected or final_marked generation errors → return `success=False`.

Implement `web/services/analysis.py`:

- Goal: Apply concept mapping (uploaded per session) to produce per-area analysis and determine strengths/improvements.

- Dataclasses:

```python
from dataclasses import dataclass
from typing import List

@dataclass
class LearningAreaResult:
    area: str
    correct: int
    total: int
    percentage: float
    is_strength: bool        # >= 51%

@dataclass
class SubjectAnalysis:
    subject: str
    strengths: List[str]
    improvements: List[str]
    area_details: List[LearningAreaResult]
    unmapped_questions: List[str]

@dataclass
class FullAnalysis:
    reading: SubjectAnalysis
    quantitative_reasoning: SubjectAnalysis
    abstract_reasoning: SubjectAnalysis
    writing_score: int
    overall_summary: str      # brief text summary (optional)
```

- Implement `AnalysisService`:

```python
class AnalysisService:
    STRENGTH_THRESHOLD = 51

    def __init__(self, concept_mapping: dict):
        self.mapping = self._clean_and_validate_mapping(concept_mapping)

    def _clean_and_validate_mapping(self, mapping: dict) -> dict:
        # Remove keys starting with "_" (instructional metadata)
        # Ensure subject → {area → [questions]} structure
        # Detect duplicates within a subject; warn/fail gracefully
        # Return cleaned mapping

    def analyze_subject_performance(self, subject: str, question_results: List[QuestionResult]) -> SubjectAnalysis:
        # Build lookup {question_label: is_correct}
        # For each area’s question list:
        #   Compute correct/total; percentage; is_strength by threshold
        # Handle questions in results not present in mapping → unmapped_questions
        # Return SubjectAnalysis

    def generate_full_analysis(self,
                               reading_result: SubjectResult,
                               qr_result: SubjectResult,
                               ar_result: SubjectResult,
                               writing_score: int) -> FullAnalysis:
        # Call analyze_subject_performance for "Reading", "Quantitative Reasoning", "Abstract Reasoning"
        # Optionally compute or craft an overall_summary text
        # Return FullAnalysis
```

Update `web/services/__init__.py` to export all classes/dataclasses.

### M3 — PDF Report & Annotated Sheets
Goal: Replace stub PDF generators with production versions.

Implement `web/services/report.py`:

- Use ReportLab (preferred) or WeasyPrint.
- Branded PDF with:
  - Everest Tutoring logo (assets/everest_logo.png) if available
  - Title “ASET Practice Exam Report”
  - Student name, writing score (manual), Reading/QR/AR scores
  - Strengths and areas for improvement per subject
  - Footer: “Everest Tutoring — Helping students reach new heights”
- Layout: consistent fonts, colors (e.g., primary blue #3498DB, dark #2C3E50).
- API:

```python
class ReportService:
    def __init__(self, assets_dir: Path): ...
    def generate_student_report(self,
                                student_name: str,
                                reading_score: SubjectResult,
                                qr_score: SubjectResult,
                                ar_score: SubjectResult,
                                writing_score: int,
                                analysis: FullAnalysis) -> bytes:
        # Return PDF bytes
```

Implement `web/services/annotator.py`:

- Take marked image (CV2 array), render overlays:
  - Red boxes for incorrect answers (optional detail: if bubble coordinates available, but at minimum include summary text overlay on image).
  - Add score text at top: “Reading: 22/30 (73.3%)”
- Convert to PDF:

```python
class AnnotatorService:
    INCORRECT_COLOR = (0, 0, 255)  # BGR red
    CORRECT_COLOR = (0, 255, 0)    # BGR green

    def annotate_sheet(self,
                       marked_image: np.ndarray,
                       question_results: List[QuestionResult],
                       subject: str,
                       score: SubjectResult) -> np.ndarray:
        # Compose final overlay as needed; return CV2 image

    def image_to_pdf_bytes(self, image: np.ndarray) -> bytes:
        # Use PIL or ReportLab to create single-page PDF bytes from image
```

### M4 — Web Backend Integration
Goal: Wire real services into routes.

Update `web/routes/marking.py`:

- Flow:
  1. Validate session (auth) and check configuration exists in session: reading answers, qrar answers, concept mapping.
  2. Read uploaded PNGs: `reading_sheet`, `qrar_sheet`.
  3. Call `MarkingService.mark_reading_sheet(...)` and `.mark_qrar_sheet(...)`.
  4. Build `AnalysisService` with session concept mapping; call `generate_full_analysis(...)`.
  5. Generate annotated PDFs with `AnnotatorService`.
  6. Generate branded report PDF with `ReportService`.
  7. Create `results.json` with structured data (scores, analysis).
  8. Package into a ZIP in memory and return via `StreamingResponse` with `Content-Disposition: attachment; filename=<student>_results.zip`.

- Handle errors with clear JSON messages (400/422 if invalid input).

Update `web/routes/batch.py`:

- Accept `manifest` JSON and `sheets_zip`.
- Parse manifest; for each student:
  - Extract files from ZIP; process via `MarkingService`.
  - Analysis via `AnalysisService`.
  - Annotated PDFs and report.
  - Write per-student folder into output ZIP (in memory).
- Return final ZIP stream.

### M5 — Web Frontend Completion
Goal: Finish cohesive UI experience.

- Ensure dashboard shows config status; enable marking mode cards only after config load.
- Single-marking page:
  - File preview for PNG uploads.
  - Async form submission; show spinner; auto-download ZIP; success message; “Mark another student”.
- Batch page:
  - Manifest upload tips; sample manifest link; spinner; downloads ZIP on success; success message.
- Refine CSS and JS for responsiveness.

### M6 — Batch Processing Robustness
- Validate manifest structure thoroughly.
- Handle missing files gracefully.
- Ensure consistent folder naming in output ZIP (e.g., “John_Smith/…”).
- Include `results.json` per student and optional summary at root.

### M7 — Testing & QA
- Unit tests:
  - `tests/test_marker_service.py`: template loading, PNG conversion, response evaluation, error handling.
  - `tests/test_analysis_service.py`: mapping validation, percentage and threshold boundary checks, unmapped questions handling.
- Integration tests:
  - Marking routes with sample PNGs and fake configs (mock CV2 ops if needed).
  - Batch routes with a tiny sample ZIP and manifest.
- End-to-end:
  - Run dev server; manual validations.
- Edge cases:
  - Multi-marked bubbles; unmarked responses; invalid PNGs; poor scan quality (optional: add heuristic warnings).

### M8 — Deployment & Documentation
- Dockerize with dependencies (OpenCV libs).
- Deploy (Railway/Render/Fly.io).
- Environment variables:
  - `STAFF_PASSWORD` (shared staff password)
  - `SECRET_KEY` (cookie signing)
- Staff documentation (login, config upload, single/batch workflows, troubleshooting).
- Handover package (source access if agreed, credentials, usage guide).

---

## 6. API Surface and Data Flows

### 6.1 Auth & Session

- `POST /login` (form-data: `password`)
  - Validates password; sets `session_token` cookie; redirects to dashboard.
- `GET /logout`
  - Clears session cookie; redirects to login.

### 6.2 Dashboard & Configuration

- `GET /` → dashboard
  - Shows configuration status.
- `POST /configure` (multipart):
  - `reading_answers`: TXT or CSV
  - `qrar_answers`: TXT or CSV
  - `concept_mapping`: JSON
  - Returns JSON summary: counts of questions; subjects mapped.

- Answer key parsing:
  - TXT: one answer per line.
  - CSV: `question,answer` pairs; we map to sequential labels (q1..qn or qr/ar sequences).

### 6.3 Marking

- `GET /mark/single` → Single student page.
- `POST /mark/single/process` (multipart):
  - `student_name`: str
  - `writing_score`: int
  - `reading_sheet`: PNG file
  - `qrar_sheet`: PNG file
  - Returns: ZIP stream with PDFs and JSON.

### 6.4 Batch

- `GET /batch`
- `POST /batch/process` (multipart):
  - `manifest`: JSON file (see format below)
  - `sheets_zip`: ZIP file with PNGs named in manifest
  - Returns: ZIP stream with per-student folders.

Manifest JSON example:
```json
{
  "students": [
    {
      "name": "John Smith",
      "writing_score": 85,
      "reading_file": "john_reading.png",
      "qrar_file": "john_qrar.png"
    },
    {
      "name": "Jane Doe",
      "writing_score": 78,
      "reading_file": "jane_reading.png",
      "qrar_file": "jane_qrar.png"
    }
  ]
}
```

---

## 7. Inputs & Outputs

### 7.1 Inputs

- Per session (uploaded once, stored in-memory):
  - Reading answer key (TXT/CSV)
  - QR/AR answer key (TXT/CSV) OR separate QR/TXT and AR/TXT if desired
  - Concept mapping (JSON: subject → areas → questions)

- Per student (single):
  - Reading sheet PNG
  - QR/AR sheet PNG
  - Student name (string)
  - Writing score (integer; manual)

- Batch:
  - `manifest.json`
  - ZIP containing all referenced PNGs

### 7.2 Outputs

- Single student ZIP contains:
  - `<student>_reading_marked.pdf`
  - `<student>_qrar_marked.pdf`
  - `<student>_report.pdf`
  - `<student>_results.json`

- Batch ZIP contains per-student folder:
  - `John_Smith/reading_marked.pdf`
  - `John_Smith/qrar_marked.pdf`
  - `John_Smith/report.pdf`
  - `John_Smith/results.json`
  - (Repeat for each student)

`results.json` recommended structure:
```json
{
  "student_name": "John Smith",
  "writing_score": 85,
  "reading": {
    "correct": 24, "incorrect": 6, "unmarked": 0, "total": 30, "percentage": 80.0,
    "questions": [
      {"question": "q1", "student_answer": "A", "correct_answer": "A", "is_correct": true, "is_unmarked": false},
      ...
    ]
  },
  "quantitative_reasoning": {
    "correct": 18, "incorrect": 7, "unmarked": 0, "total": 25, "percentage": 72.0,
    "questions": [ ... ]
  },
  "abstract_reasoning": {
    "correct": 14, "incorrect": 6, "unmarked": 0, "total": 20, "percentage": 70.0,
    "questions": [ ... ]
  },
  "analysis": {
    "Reading": {
      "strengths": ["Vocabulary in Context", ...],
      "improvements": ["Inference & Interpretation", ...],
      "area_details": [
        {"area": "Vocabulary in Context", "correct": 5, "total": 6, "percentage": 83.3, "is_strength": true},
        ...
      ],
      "unmapped_questions": []
    },
    "Quantitative Reasoning": { ... },
    "Abstract Reasoning": { ... }
  }
}
```

---

## 8. Guardrails and Constraints (for LLM)

The LLM MUST adhere to the following:

- Do NOT modify files under `src/*` unless absolutely necessary. Prefer wrappers and integrations in `web/services/*` and `web/routes/*`.

- PNG-only: Validate uploaded files; reject non-PNG inputs.

- Session-based configuration: `reading_answers`, `qrar_answers`, `concept_mapping` are stored in-memory per staff session. No database or persistent storage.

- No student data retention: Do not store student data or outputs on disk beyond preparing a ZIP for immediate download. If temporary files are needed, clean them up promptly.

- Implement robust error handling and user-friendly messages:
  - Missing template files
  - Invalid PNG images
  - Preprocessor failure
  - Missing manifest entries in batch mode
  - Concept mapping validation errors (e.g., duplicates)

- Use Python type hints and dataclasses for structured models.

- Keep outputs consistent with the client brief (annotated PDFs, branded report PDF, results JSON; all in a ZIP).

---

## 9. Acceptance Criteria

The project is considered complete when:

- Staff can log in using a pre-defined password and upload session configuration (answer keys + concept mapping).
- Single student mode:
  - Upload Reading + QR/AR PNGs, enter name and writing score
  - Receive a ZIP containing annotated PDFs, report PDF, and JSON results
- Batch mode:
  - Upload ZIP of PNGs + manifest JSON
  - Receive a batch ZIP with per-student folders containing annotated PDFs, report PDF, and results JSON
- Bubble detection is reliable for ASET sheet scans as per the validated templates:
  - Incorrect answers highlighted in annotated PDFs
  - Scores computed correctly per subject
- Strengths/weaknesses per subject computed from the uploaded concept mapping (≥51% threshold).
- No permanent storage of student data; in-memory processing only.
- Hosting-ready (Dockerized); simple environment variables for password and secret key.

---

## 10. Testing Plan

- Unit tests:
  - `tests/test_marker_service.py`: Template loading, PNG validation, image conversion, response evaluation, error handling paths.
  - `tests/test_analysis_service.py`: Mapping validation, per-area percentages, 51% threshold boundary cases (50%, 51%, 52%), unmapped handling.

- Integration tests:
  - `tests/test_routes.py`: Login, configuration upload, single student marking with tiny PNG samples; verify streaming ZIP responses.
  - Batch route test with micro ZIP and manifest.

- Manual UAT:
  - Use actual ASET PNG scans from client.
  - Test multiple sheets, varying quality.
  - Confirm error messages and guidance where needed.

---

## 11. Deployment Plan

- Dockerfile:
  - Python 3.11 slim
  - System deps for OpenCV (libgl, glib, etc.)
  - Expose port 8000; run `uvicorn web.app:app --host 0.0.0.0 --port 8000`.

- Hosting:
  - Railway/Render/Fly.io recommended (budget ~ $5/month).
  - Set environment variables:
    - `STAFF_PASSWORD`
    - `SECRET_KEY`
    - Optional: `DEBUG`, `SESSION_DURATION_HOURS`

- TLS/Domain:
  - Most platforms provide auto-HTTPS (optional custom domain).

- Staff documentation:
  - Login steps
  - Uploading configuration
  - Single student and batch workflows
  - Formatting of answer keys and concept mapping
  - Troubleshooting common issues

---

## 12. Reference Templates & Samples (include these for the LLM)

Paste your finalized `config/aset_reading_template.json` and `config/aset_qrar_template.json` contents here to give the LLM exact layouts (replace with your real measured values):

```json
{
  "pageDimensions": [1700, 2200],
  "bubbleDimensions": [32, 30],
  "emptyValue": "",
  "preProcessors": [
    { "name": "CropPage", "options": { "morphKernel": [10, 10] } }
  ],
  "fieldBlocks": {
    "ReadingColumn1": {
      "origin": [148, 285],
      "bubblesGap": 45,
      "labelsGap": 38,
      "fieldLabels": ["q1..q15"],
      "bubbleValues": ["A", "B", "C", "D"],
      "direction": "vertical"
    },
    "ReadingColumn2": {
      "origin": [548, 285],
      "bubblesGap": 45,
      "labelsGap": 38,
      "fieldLabels": ["q16..q30"],
      "bubbleValues": ["A", "B", "C", "D"],
      "direction": "vertical"
    }
  },
  "customLabels": {},
  "outputColumns": ["q1..q30"]
}
```

```json
{
  "pageDimensions": [1700, 2200],
  "bubbleDimensions": [32, 30],
  "emptyValue": "",
  "preProcessors": [
    { "name": "CropPage", "options": { "morphKernel": [10, 10] } }
  ],
  "fieldBlocks": {
    "QuantitativeReasoning": {
      "origin": [150, 250],
      "bubblesGap": 42,
      "labelsGap": 36,
      "fieldLabels": ["qr1..qr25"],
      "bubbleValues": ["A", "B", "C", "D", "E"],
      "direction": "vertical"
    },
    "AbstractReasoning": {
      "origin": [150, 1200],
      "bubblesGap": 42,
      "labelsGap": 36,
      "fieldLabels": ["ar1..ar20"],
      "bubbleValues": ["A", "B", "C", "D", "E"],
      "direction": "vertical"
    }
  },
  "customLabels": {},
  "outputColumns": ["qr1..qr25", "ar1..ar20"]
}
```

Sample concept mapping (staff will upload dynamically per session; include for testing):

```json
{
  "_instructions": "Each question should appear in exactly one area per subject.",
  "_threshold_note": "≥51% = Done well; <51% = Needs improvement",
  "Reading": {
    "Main Idea & Theme": ["q1","q6","q11","q16","q21","q26"],
    "Inference & Interpretation": ["q2","q7","q12","q17","q22","q27"],
    "Vocabulary in Context": ["q3","q8","q13","q18","q23","q28"],
    "Author's Purpose & Tone": ["q4","q9","q14","q19","q24","q29"],
    "Text Structure & Features": ["q5","q10","q15","q20","q25","q30"]
  },
  "Quantitative Reasoning": {
    "Number & Operations": ["qr1","qr2","qr3","qr4","qr5"],
    "Algebra & Patterns": ["qr6","qr7","qr8","qr9","qr10"],
    "Measurement": ["qr11","qr12","qr13","qr14","qr15"],
    "Geometry & Spatial Sense": ["qr16","qr17","qr18","qr19","qr20"],
    "Statistics & Probability": ["qr21","qr22","qr23","qr24","qr25"]
  },
  "Abstract Reasoning": {
    "Pattern Recognition": ["ar1","ar2","ar3","ar4","ar5","ar6","ar7"],
    "Spatial Reasoning": ["ar8","ar9","ar10","ar11","ar12","ar13"],
    "Logical Sequences": ["ar14","ar15","ar16","ar17","ar18","ar19","ar20"]
  }
}
```

Sample answer keys (TXT):
```
A
B
C
D
A
B
C
D
A
B
C
D
A
B
C
D
A
B
C
D
A
B
C
D
A
B
C
D
A
B
```

Sample answer keys (CSV):
```csv
q1,A
q2,B
q3,C
q4,D
q5,A
q6,B
q7,C
q8,D
q9,A
q10,B
q11,C
q12,D
q13,A
q14,B
q15,C
q16,D
q17,A
q18,B
q19,C
q20,D
q21,A
q22,B
q23,C
q24,D
q25,A
q26,B
q27,C
q28,D
q29,A
q30,B
```

---

## 13. Next Actions for the LLM

- Implement M2:
  - Complete `web/services/marker.py` and `web/services/analysis.py` per specs above.
  - Update `web/services/__init__.py` to export dataclasses and services.
- Implement M3:
  - Complete `web/services/report.py` and `web/services/annotator.py`.
- Implement M4–M6:
  - Wire services into `web/routes/marking.py` and `web/routes/batch.py`.
  - Ensure ZIP streaming responses, robust manifest handling.
- Implement M7:
  - Add unit and integration tests.
- Implement M8:
  - Deployment artifacts and staff documentation.

Remember:
- Use file blocks in responses when proposing code (with exact file paths).
- Do not alter src/* unless strictly necessary; wrap their functionality.
- Maintain constraints (PNG-only, session-based configuration, no persistence).
- Return outputs exactly as ZIPs with PDFs + JSON.

---

## 14. Context Metadata (for the LLM)

- Current Date: 2026-01-03
- User/GitHub login: atu1ya
- Repo: https://github.com/atu1ya/ASETmarker

This document is the authoritative specification for continuing development. Pick up from Milestone 2 and proceed through Milestone 8, complying with constraints and acceptance criteria.