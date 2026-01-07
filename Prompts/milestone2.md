# ASET Marking System - Milestone 2: Core Marking Services

## Role & Objective
Act as a Senior Python Backend Developer. We are building the "Everest Tutoring ASET Marking System". 
**Your task is to complete Milestone 2 (M2):** Implementing the core service layer that wraps our legacy OMR engine.

## Context
- **Existing Engine:** We have a legacy OMR engine in `src/`. **You MUST NOT modify any file in `src/`.** You must import and use the classes as defined below.
- **Web Layer:** We are building the web services in `web/services/`.
- **Templates:** JSON templates are located in `config/`.
- **Input:** Raw PNG image bytes.
- **Output:** Structured scoring results and annotated image arrays (in-memory).

## Required Engine Interfaces (Do not hallucinate signatures)
You must utilize these specific components from the `src` directory:

1.  **`src.template.Template`**:
    - `__init__(self, template_path, tuning_config)`
    - *Note:* Requires `template_path` (Path object) and `tuning_config` (DotMap).

2.  **`src.core.ImageInstanceOps`**:
    - `__init__(self, tuning_config)`
    - `apply_preprocessors(self, file_path, image, template) -> processed_image`
    - `read_omr_response(self, template, image, name) -> (omr_response, final_marked, multi_marked, multi_roll)`
    - *Note:* `omr_response` is a dict of `{label: value}`. `final_marked` is the visual output.

3.  **`src.utils.parsing.get_concatenated_response`**:
    - `get_concatenated_response(omr_response, template) -> dict`
    - *Use this to normalize the output.*

4.  **`src.defaults.CONFIG_DEFAULTS`**:
    - Import this and wrap it in `dotmap.DotMap` to create the configuration object.

5.  **`src.processors.FeatureBasedAlignment.FeatureBasedAlignment`**:
    - **CRITICAL:** You must import this class and register it into `src.processors.manager.PROCESSOR_MANAGER` manually at the top of your service file. The legacy engine does not auto-register it, but our templates use it.

## Implementation Tasks

Generate the following 3 files with production-grade code, type hinting, and error handling.

### 1. `web/services/marker.py`

**Responsibilities:**
- Define dataclasses: `QuestionResult` and `SubjectResult`.
- Implement `MarkingService`.
- **Logic Flow:**
  1. Initialize config with `DotMap(CONFIG_DEFAULTS)`. Set `outputs.save_image_level = 0` to prevent disk writes.
  2. In `process_single_subject`:
     - Decode input bytes to OpenCV grayscale image.
     - Register `FeatureBasedAlignment` into `PROCESSOR_MANAGER`.
     - Load `Template` from the provided path.
     - Instantiate `ImageInstanceOps`.
     - Run `apply_preprocessors` (pass a dummy string for `file_path`).
     - Run `read_omr_response` (pass a dummy string for `name`).
     - Run `get_concatenated_response` to get clean answers.
     - **Scoring:** Compare detected values against the `answer_key` (dict).
     - Return a `SubjectResult` containing the score, raw results, and the marked image array.

**Dataclasses:**
```python
@dataclass
class QuestionResult:
    label: str
    marked_value: str
    correct_value: str
    is_correct: bool

@dataclass
class SubjectResult:
    subject_name: str
    score: int
    total_questions: int
    results: List[QuestionResult]
    omr_response: Dict[str, str]
    marked_image: Any = field(repr=False) # numpy array

```
2. web/services/analysis.py
Responsibilities:

Define dataclasses: LearningAreaResult and FullAnalysis.

Implement AnalysisService.

Business Logic:

Threshold: A percentage >= 51.0% is "Done well". Below is "Needs improvement".

Concept Mapping: The service receives a concept_map dictionary (e.g., {"q1": "Algebra"}).

Aggregation: Group questions by Concept, calculate correct/total, apply threshold.

Compiling: compile_full_analysis should take Reading and QR/AR results and combine them into a FullAnalysis summary.

3. web/services/__init__.py
Responsibilities:

Export MarkingService, AnalysisService, and all relevant dataclasses so they can be imported via from web.services import ....

Constraints & Edge Cases
Alignment: Ensure the Template is initialized with the correct path so it can find the reference_*.jpg files located in config/.

Validation: Raise ValueError if image bytes cannot be decoded.

Dependencies: Use cv2, numpy, dotmap, dataclasses.

No Disk I/O: Do not save images to disk; keep them in memory.

Generate the complete code for these 3 files.