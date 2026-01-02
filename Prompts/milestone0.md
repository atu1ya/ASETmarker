# ASET Marking System - Milestone 0: Project Setup & Foundation

## Context

I am building a web-based automated marking system for ASET (Academic Selective Entrance Test) practice exams for a tutoring company called "Everest Tutoring". 

The system is built on top of an existing OMRChecker codebase (located in `src/` directory) that handles optical mark recognition using OpenCV.  I need to extend this with a web application layer. 

**Key Design Decisions:**
- Staff upload answer keys and concept mapping EACH SESSION (not hardcoded)
- No database - all processing in-memory per session
- Simple password authentication (single shared password for all staff)
- PNG image uploads, PDF outputs
- ZIP file downloads containing all results

## Tech Stack

- **Backend:** FastAPI
- **Frontend:** Jinja2 templates with vanilla HTML/CSS/JS
- **PDF Generation:** ReportLab
- **Existing OMR Logic:** Python with OpenCV (already in `src/` folder)
- **Deployment Target:** Railway/Render (~$5/month hosting)

## Project Structure

Generate a complete project setup with the following structure and ALL files fully implemented:

```
ASETmarker/
├── src/                          # [EXISTING - DO NOT MODIFY]
│   └── ...  (existing OMR code)
├── web/
│   ├── __init__.py
│   ├── app.py                    # FastAPI application entry point
│   ├── auth. py                   # Password-based authentication
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
│   │   ├── marker. py             # OMR marking service wrapper
│   │   ├── analysis.py           # Strengths/weaknesses analysis
│   │   ├── report.py             # PDF report generation
│   │   └── annotator.py          # Annotated sheet generation
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   └── app.js
│   │   └── images/
│   │       └── . gitkeep
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── single. html
│       ├── batch.html
│       └── components/
│           ├── navbar.html
│           ├── flash. html
│           └── footer.html
├── config/
│   ├── __init__.py
│   └── . gitkeep                  # Templates will be added in Milestone 1
├── assets/
│   ├── . gitkeep
│   └── fonts/
│       └── . gitkeep
├── docs/
│   ├── sample_answer_key.txt     # Sample for client reference
│   ├── sample_answer_key.csv     # Sample CSV format
│   └── sample_concept_mapping.json  # Sample for client reference
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_services.py
│   └── test_routes.py
├── scripts/
│   ├── run_dev.py
│   ├── setup_env.py
│   └── measure_template.py       # Template measurement helper
├── . env. example
├── .gitignore
├── requirements.txt
├── requirements. dev.txt
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── DEVELOPMENT.md
```

## Detailed File Specifications

### 1. `web/__init__.py`

```python
"""
ASET Marking System - Web Application Package
Automated marking system for Everest Tutoring. 
"""
__version__ = "1.0.0"
__author__ = "Everest Tutoring"
```

### 2. `web/config.py`

Create configuration using pydantic-settings: 
- `SECRET_KEY`: For session signing (from env)
- `STAFF_PASSWORD`: Shared staff password (from env, default "everest2024")
- `DEBUG`: Boolean for debug mode
- `SESSION_DURATION_HOURS`: Default 8 hours
- `MAX_UPLOAD_SIZE_MB`: Default 50MB
- `ALLOWED_EXTENSIONS`: [". png"]
- `CONFIG_DIR`: Path to config directory
- `ASSETS_DIR`: Path to assets directory

Include a `get_settings()` function with lru_cache. 

### 3. `web/session_store.py`

Create in-memory session storage for marking configurations: 

```python
"""
In-memory storage for session-based marking configurations.
Each staff session can have its own answer keys and concept mapping.
Data is lost on server restart (by design - no persistent storage).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import threading

@dataclass
class MarkingConfiguration:
    """Stores uploaded marking configuration for a session."""
    reading_answers: list[str] = field(default_factory=list)
    qrar_answers: list[str] = field(default_factory=list)
    concept_mapping: dict = field(default_factory=dict)
    uploaded_at: datetime = field(default_factory=datetime.now)
    
    @property
    def is_configured(self) -> bool:
        return bool(self.reading_answers and self.qrar_answers and self. concept_mapping)

class SessionConfigStore:
    """Thread-safe storage for session configurations."""
    
    def __init__(self):
        self._configs:  dict[str, MarkingConfiguration] = {}
        self._lock = threading.Lock()
    
    def get(self, session_token: str) -> Optional[MarkingConfiguration]: 
        with self._lock:
            return self._configs.get(session_token)
    
    def set(self, session_token: str, config: MarkingConfiguration):
        with self._lock:
            self._configs[session_token] = config
    
    def delete(self, session_token: str):
        with self._lock:
            self._configs.pop(session_token, None)
    
    def cleanup_expired(self, max_age_hours: int = 24):
        """Remove configurations older than max_age_hours."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        with self._lock:
            expired = [k for k, v in self._configs.items() if v.uploaded_at < cutoff]
            for k in expired:
                del self._configs[k]

# Global instance
config_store = SessionConfigStore()
```

### 4. `web/app.py`

Create FastAPI application: 
- Mount static files at `/static`
- Set up Jinja2Templates from `web/templates`
- Add session middleware using itsdangerous for signed cookies
- Include routers:  auth (no prefix), dashboard (`/`), marking (`/mark`), batch (`/batch`)
- Health check endpoint at `/health` returning `{"status": "healthy", "version": "1.0.0"}`
- Custom exception handlers for 401, 404, 500
- Startup event to log application start
- CORS middleware for development

### 5. `web/auth.py`

Create authentication system:
- Use SHA-256 for password hashing
- `verify_password(password:  str) -> bool`
- `create_session() -> str` using secrets. token_urlsafe(32)
- `validate_session(token: str) -> bool`
- `invalidate_session(token: str)`
- Store sessions in dict with expiry datetime
- `cleanup_expired_sessions()` function
- Session duration from config (default 8 hours)

### 6. `web/dependencies.py`

Create FastAPI dependencies:
- `get_settings()` - returns Settings instance
- `get_current_session(request:  Request)` - extracts and validates session from cookie, raises HTTPException 401 if invalid
- `get_optional_session(request: Request)` - returns session token or None
- `get_marking_config(session_token: str = Depends(get_current_session))` - returns MarkingConfiguration, raises 400 if not configured
- `require_configuration(config:  MarkingConfiguration = Depends(get_marking_config))` - raises HTTPException if not configured

### 7. `web/routes/__init__.py`

```python
"""Route modules for ASET Marking System."""
from web.routes import auth, dashboard, marking, batch

__all__ = ["auth", "dashboard", "marking", "batch"]
```

### 8. `web/routes/auth.py`

Create authentication routes:
- `GET /login` - render login page, redirect to dashboard if already authenticated
- `POST /login` - validate password, create session, set HTTP-only cookie, redirect to dashboard
- `GET /logout` - invalidate session, delete cookie, redirect to login
- Use Form(... ) for password field
- Flash messages for errors

### 9. `web/routes/dashboard.py`

Create dashboard routes:
- `GET /` - render dashboard with configuration status
- `GET /dashboard` - alias redirect to `/`
- `POST /configure` - handle multipart form upload of: 
  - `reading_answers`: UploadFile (txt or csv)
  - `qrar_answers`: UploadFile (txt or csv)  
  - `concept_mapping`: UploadFile (json)
- Parse and validate uploads
- Store in SessionConfigStore
- Return JSON response with status and summary

Include helper functions:
- `parse_answer_key(content: str) -> list[str]` - handles both line-per-answer and CSV formats
- `validate_concept_mapping(concepts:  dict) -> list[str]` - returns list of validation errors
- `get_configuration_status(session_token: str) -> dict` - returns current config summary

### 10. `web/routes/marking.py`

Create single student marking routes:
- `GET /mark/single` - render single marking page (requires auth + config)
- `POST /mark/single/process` - process uploaded sheets: 
  - Accept:  `student_name` (Form), `writing_score` (Form int), `reading_sheet` (UploadFile), `qrar_sheet` (UploadFile)
  - Validate files are PNG
  - Call marking service
  - Call analysis service
  - Generate annotated PDFs
  - Generate student report PDF
  - Generate results JSON
  - Package all into ZIP
  - Return StreamingResponse with ZIP

### 11. `web/routes/batch.py`

Create batch processing routes:
- `GET /batch` - render batch page (requires auth + config)
- `POST /batch/process` - process batch upload:
  - Accept: `manifest` (UploadFile JSON), `sheets_zip` (UploadFile ZIP)
  - Validate manifest format
  - Extract ZIP
  - Process each student
  - Package results into ZIP with per-student folders
  - Return StreamingResponse

Manifest format:
```json
{
  "students": [
    {
      "name": "John Smith",
      "writing_score": 85,
      "reading_file": "john_reading.png",
      "qrar_file": "john_qrar.png"
    }
  ]
}
```

### 12. `web/services/__init__.py`

```python
"""Service layer for ASET Marking System."""
from web.services.marker import MarkingService
from web.services.analysis import AnalysisService
from web.services.report import ReportService
from web.services.annotator import AnnotatorService

__all__ = ["MarkingService", "AnalysisService", "ReportService", "AnnotatorService"]
```

### 13. `web/services/marker.py`

Create marking service (STUB for now - will be implemented in M2):

```python
"""
Marking service that wraps the existing OMR logic. 
STUB IMPLEMENTATION - Full implementation in Milestone 2.
"""
from pathlib import Path
from typing import Optional
import numpy as np

class MarkingService:
    """Service for processing OMR sheets and extracting responses."""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self. reading_template = None
        self.qrar_template = None
    
    def initialize_templates(self):
        """Load OMR templates from config directory."""
        # STUB - will load actual templates in M2
        pass
    
    def mark_reading_sheet(
        self, 
        image_bytes: bytes,
        answer_key: list[str]
    ) -> dict:
        """
        Process a reading sheet and return results.
        
        Returns:
            dict with keys:
            - responses: dict[str, str] - detected answers per question
            - results: dict - scoring results
            - marked_image: np.ndarray - annotated image
            - multi_marked:  bool - whether multi-marking detected
        """
        # STUB - return dummy data for testing UI
        num_questions = len(answer_key)
        responses = {f"q{i+1}": answer_key[i] for i in range(num_questions)}
        
        return {
            "responses": responses,
            "results": {
                "subject": "Reading",
                "correct":  num_questions,
                "total": num_questions,
                "percentage": 100.0,
                "questions": [
                    {
                        "question": f"q{i+1}",
                        "student_answer": answer_key[i],
                        "correct_answer": answer_key[i],
                        "is_correct": True
                    }
                    for i in range(num_questions)
                ]
            },
            "marked_image": np.zeros((100, 100), dtype=np.uint8),
            "multi_marked": False
        }
    
    def mark_qrar_sheet(
        self,
        image_bytes: bytes,
        answer_key: list[str]
    ) -> dict:
        """Process a QR/AR sheet and return results."""
        # STUB - similar to reading
        num_questions = len(answer_key)
        
        # Split into QR and AR (assuming first 25 are QR, rest are AR)
        qr_count = min(25, num_questions)
        ar_count = num_questions - qr_count
        
        return {
            "qr":  {
                "subject": "Quantitative Reasoning",
                "correct": qr_count,
                "total": qr_count,
                "percentage": 100.0,
                "questions": [
                    {
                        "question": f"qr{i+1}",
                        "student_answer": answer_key[i],
                        "correct_answer": answer_key[i],
                        "is_correct": True
                    }
                    for i in range(qr_count)
                ]
            },
            "ar":  {
                "subject": "Abstract Reasoning",
                "correct":  ar_count,
                "total": ar_count,
                "percentage": 100.0,
                "questions": [
                    {
                        "question": f"ar{i+1}",
                        "student_answer":  answer_key[qr_count + i],
                        "correct_answer": answer_key[qr_count + i],
                        "is_correct": True
                    }
                    for i in range(ar_count)
                ]
            },
            "marked_image": np.zeros((100, 100), dtype=np.uint8),
            "multi_marked": False
        }
```

### 14. `web/services/analysis.py`

Create analysis service (STUB for now - will be implemented in M2):

```python
"""
Analysis service for calculating strengths and weaknesses.
STUB IMPLEMENTATION - Full implementation in Milestone 2.
"""

class AnalysisService: 
    """Analyzes student performance by learning area."""
    
    STRENGTH_THRESHOLD = 51  # percentage
    
    def __init__(self, concept_mapping: dict):
        self.concept_mapping = self._clean_mapping(concept_mapping)
    
    def _clean_mapping(self, mapping: dict) -> dict:
        """Remove instruction keys (starting with _)."""
        return {k:  v for k, v in mapping. items() if not k.startswith('_')}
    
    def analyze_performance(
        self,
        subject: str,
        question_results: list[dict]
    ) -> dict:
        """
        Analyze performance by learning area.
        
        Returns:
            dict with keys: 
            - strengths: list[str] - areas with >= 51% correct
            - improvements: list[str] - areas with < 51% correct
            - details: list[dict] - per-area breakdown
        """
        if subject not in self.concept_mapping:
            return {"strengths": [], "improvements": [], "details": []}
        
        results_lookup = {r["question"]: r["is_correct"] for r in question_results}
        
        strengths = []
        improvements = []
        details = []
        
        for area, questions in self.concept_mapping[subject].items():
            correct = sum(1 for q in questions if results_lookup. get(q, False))
            total = len(questions)
            percentage = (correct / total * 100) if total > 0 else 0
            
            details.append({
                "area":  area,
                "correct": correct,
                "total": total,
                "percentage": round(percentage, 1)
            })
            
            if percentage >= self.STRENGTH_THRESHOLD:
                strengths.append(area)
            else:
                improvements.append(area)
        
        return {
            "strengths": strengths,
            "improvements": improvements,
            "details": details
        }
    
    def generate_full_analysis(
        self,
        reading_results: dict,
        qr_results: dict,
        ar_results: dict,
        writing_score: int
    ) -> dict:
        """Generate complete analysis across all subjects."""
        return {
            "Reading": self.analyze_performance("Reading", reading_results. get("questions", [])),
            "Quantitative Reasoning": self.analyze_performance("Quantitative Reasoning", qr_results.get("questions", [])),
            "Abstract Reasoning":  self.analyze_performance("Abstract Reasoning", ar_results.get("questions", [])),
            "Writing": {
                "score": writing_score,
                "note": "Manually assessed"
            }
        }
```

### 15. `web/services/report.py`

Create report service (STUB for now - will be implemented in M3):

```python
"""
PDF report generation service.
STUB IMPLEMENTATION - Full implementation in Milestone 3.
"""
from pathlib import Path
from io import BytesIO

class ReportService:
    """Generates branded PDF reports for students."""
    
    def __init__(self, assets_dir: Path):
        self.assets_dir = assets_dir
        self.logo_path = assets_dir / "everest_logo.png"
    
    def generate_student_report(
        self,
        student_name: str,
        reading_score: dict,
        qr_score:  dict,
        ar_score:  dict,
        writing_score:  int,
        analysis: dict
    ) -> bytes:
        """
        Generate a complete student report PDF.
        
        STUB:  Returns a minimal valid PDF for testing. 
        """
        # Minimal PDF for stub
        pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >> stream
BT /F1 12 Tf 100 700 Td (STUB REPORT) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer << /Size 5 /Root 1 0 R >>
startxref
307
%%EOF"""
        return pdf_content
```

### 16. `web/services/annotator.py`

Create annotator service (STUB for now - will be implemented in M3):

```python
"""
Annotated sheet generation service.
STUB IMPLEMENTATION - Full implementation in Milestone 3.
"""
import numpy as np
from io import BytesIO

class AnnotatorService:
    """Generates annotated marked sheets highlighting correct/incorrect answers."""
    
    INCORRECT_COLOR = (0, 0, 255)  # Red in BGR
    CORRECT_COLOR = (0, 255, 0)    # Green in BGR
    
    def annotate_sheet(
        self,
        marked_image: np.ndarray,
        question_results: list[dict],
        subject: str,
        score: dict
    ) -> np.ndarray:
        """
        Annotate a marked sheet with visual indicators.
        
        STUB: Returns the image as-is. 
        """
        return marked_image
    
    def image_to_pdf_bytes(self, image: np. ndarray) -> bytes:
        """
        Convert image to PDF bytes. 
        
        STUB: Returns minimal valid PDF.
        """
        pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 47 >> stream
BT /F1 12 Tf 100 700 Td (STUB ANNOTATED) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer << /Size 5 /Root 1 0 R >>
startxref
310
%%EOF"""
        return pdf_content
```

### 17. `web/templates/base.html`

Create base template:
- HTML5 doctype with lang="en"
- Meta charset UTF-8, viewport for responsiveness
- Title block:  `{% block title %}ASET Marking System{% endblock %}`
- Link to `/static/css/style.css`
- Include `components/navbar.html` (with conditional for authenticated)
- Include `components/flash. html`
- Main content block: `{% block content %}{% endblock %}`
- Include `components/footer.html`
- Script block: `{% block scripts %}{% endblock %}`
- Link to `/static/js/app.js`

### 18. `web/templates/login.html`

Create login page extending base. html:
- Centered card container
- Everest Tutoring logo placeholder (use text if no image)
- "ASET Marking System" title
- "Staff Login" subtitle
- Password input field with placeholder "Enter staff password"
- Submit button "Login"
- Error message display using flash
- Clean, professional styling

### 19. `web/templates/dashboard.html`

Create dashboard extending base.html:
- Welcome header "ASET Marking System Dashboard"
- Configuration status card showing: 
  - Whether configured (green checkmark) or not (yellow warning)
  - If configured: number of reading questions, qrar questions, subjects mapped
- Step 1 card: "Load Marking Configuration"
  - Form with enctype="multipart/form-data"
  - File input:  Reading Answer Key (accept . txt,. csv)
  - File input: QR/AR Answer Key (accept .txt,.csv)
  - File input: Concept Mapping (accept .json)
  - Submit button "Load Configuration"
  - Help text with link to sample files
- Step 2 card:  "Choose Marking Mode" (only visible if configured)
  - Two clickable cards side by side: 
    - "Single Student" - link to /mark/single
    - "Batch Processing" - link to /batch
- JavaScript to handle form submission via fetch and update status

### 20. `web/templates/single. html`

Create single marking page extending base.html:
- Title "Single Student Marking"
- Back link to dashboard
- Configuration reminder showing current config summary
- Form with enctype="multipart/form-data": 
  - Student Name text input (required)
  - Writing Score number input (min=0, max=100, required)
  - Reading Sheet file input (accept=".png", required)
  - QR/AR Sheet file input (accept=".png", required)
  - Image preview areas for uploaded files
- Submit button "Mark & Generate Report" with loading state
- Results section (hidden initially):
  - Success message
  - "Download should start automatically"
  - "Mark Another Student" button to reset form
- JavaScript for form handling, preview, and download

### 21. `web/templates/batch.html`

Create batch processing page extending base.html:
- Title "Batch Processing"
- Back link to dashboard
- Instructions section explaining manifest format
- Downloadable sample manifest template
- Form: 
  - Manifest JSON file input
  - Sheets ZIP file input
- Submit button with progress indicator
- Results section with download area
- JavaScript for handling

### 22. `web/templates/components/navbar.html`

Create navbar component:
- Dark background (#2C3E50)
- Left:  Logo/brand "ASET Marking System"
- Center: Nav links (if authenticated): Dashboard, Single Marking, Batch Processing
- Right:  Logout button (if authenticated)
- Responsive hamburger menu for mobile

### 23. `web/templates/components/flash.html`

Create flash messages component:
- Container for flash messages
- Support types: success (green), error (red), warning (yellow), info (blue)
- Each message has dismiss X button
- Auto-dismiss after 5 seconds (via JS)
- Slide-in animation

### 24. `web/templates/components/footer.html`

Create footer: 
- Light gray background
- Centered text
- "© 2024 Everest Tutoring"
- "Helping students reach new heights"
- Small, unobtrusive

### 25. `web/static/css/style.css`

Create comprehensive stylesheet (500+ lines):

```css
/* CSS Custom Properties */
:root {
    --primary:  #3498DB;
    --primary-dark: #2980B9;
    --secondary: #2C3E50;
    --success: #27AE60;
    --success-light: #d4edda;
    --danger: #E74C3C;
    --danger-light: #f8d7da;
    --warning:  #F39C12;
    --warning-light: #fff3cd;
    --info: #17a2b8;
    --info-light: #d1ecf1;
    --light: #ECF0F1;
    --dark: #2C3E50;
    --white: #FFFFFF;
    --gray-100: #f8f9fa;
    --gray-200: #e9ecef;
    --gray-300: #dee2e6;
    --gray-400: #ced4da;
    --gray-500: #adb5bd;
    --gray-600: #6c757d;
    --gray-700: #495057;
    --gray-800: #343a40;
    --gray-900: #212529;
    
    --font-family:  'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    --border-radius: 8px;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow:  0 2px 10px rgba(0,0,0,0.1);
    --shadow-lg: 0 10px 25px rgba(0,0,0,0.15);
    --transition: all 0.2s ease;
}

/* Reset */
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

/* Base */
html {
    font-size: 16px;
    scroll-behavior: smooth;
}

body {
    font-family:  var(--font-family);
    background:  var(--light);
    color: var(--gray-800);
    line-height: 1.6;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

main {
    flex: 1;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    line-height: 1.3;
    margin-bottom: 0.5rem;
    color: var(--secondary);
}

h1 { font-size: 2rem; }
h2 { font-size: 1.5rem; }
h3 { font-size: 1.25rem; }

p { margin-bottom: 1rem; }

a {
    color: var(--primary);
    text-decoration:  none;
    transition: var(--transition);
}

a:hover {
    color: var(--primary-dark);
    text-decoration: underline;
}

/* Navbar */
.navbar {
    background: var(--secondary);
    color: var(--white);
    padding: 1rem 2rem;
    display: flex;
    align-items: center;
    gap: 2rem;
    box-shadow: var(--shadow);
    position: sticky;
    top: 0;
    z-index: 1000;
}

.navbar-brand {
    font-size: 1.25rem;
    font-weight:  600;
    color: var(--white);
    text-decoration: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.navbar-brand:hover {
    color: var(--white);
    text-decoration: none;
}

.navbar-nav {
    display: flex;
    gap: 1. 5rem;
    list-style: none;
    flex:  1;
}

.navbar-nav a {
    color:  rgba(255,255,255,0.8);
    text-decoration: none;
    padding: 0.5rem 0;
    border-bottom: 2px solid transparent;
    transition: var(--transition);
}

.navbar-nav a:hover,
.navbar-nav a.active {
    color: var(--white);
    border-bottom-color: var(--primary);
}

.navbar-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    font-weight: 500;
    border: none;
    border-radius: var(--border-radius);
    cursor: pointer;
    transition: var(--transition);
    text-decoration: none;
}

.btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.btn-primary {
    background: var(--primary);
    color: var(--white);
}

.btn-primary:hover: not(:disabled) {
    background: var(--primary-dark);
}

.btn-success {
    background: var(--success);
    color: var(--white);
}

.btn-success:hover:not(:disabled) {
    background: #219a52;
}

.btn-danger {
    background: var(--danger);
    color: var(--white);
}

.btn-outline {
    background: transparent;
    border: 2px solid var(--gray-300);
    color: var(--gray-700);
}

.btn-outline:hover {
    border-color: var(--primary);
    color: var(--primary);
}

.btn-sm {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
}

.btn-lg {
    padding: 1rem 2rem;
    font-size: 1.125rem;
}

.btn-block {
    width: 100%;
}

/* Cards */
.card {
    background: var(--white);
    border-radius: var(--border-radius);
    box-shadow: var(--shadow);
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

.card-header {
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom:  1px solid var(--gray-200);
}

.card-title {
    margin-bottom: 0.25rem;
}

.card-subtitle {
    color: var(--gray-600);
    font-size: 0.875rem;
}

/* Forms */
.form-group {
    margin-bottom: 1.25rem;
}

.form-label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: var(--gray-700);
}

.form-control {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    border: 2px solid var(--gray-300);
    border-radius: var(--border-radius);
    transition: var(--transition);
    background: var(--white);
}

.form-control:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
}

.form-control:: placeholder {
    color: var(--gray-500);
}

.form-text {
    font-size: 0.875rem;
    color: var(--gray-600);
    margin-top: 0.25rem;
}

.form-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
}

/* File Input */
.file-input-wrapper {
    position: relative;
    border: 2px dashed var(--gray-300);
    border-radius: var(--border-radius);
    padding: 2rem;
    text-align: center;
    transition: var(--transition);
    cursor: pointer;
}

. file-input-wrapper:hover {
    border-color: var(--primary);
    background: rgba(52, 152, 219, 0.05);
}

.file-input-wrapper input[type="file"] {
    position: absolute;
    top:  0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    cursor:  pointer;
}

.file-input-wrapper . file-icon {
    font-size: 2rem;
    color: var(--gray-400);
    margin-bottom: 0.5rem;
}

. file-input-wrapper .file-text {
    color: var(--gray-600);
}

.file-input-wrapper . file-name {
    margin-top: 0.5rem;
    font-weight: 500;
    color: var(--success);
}

/* Image Preview */
.image-preview {
    max-width: 100%;
    max-height: 200px;
    margin-top: 1rem;
    border-radius: var(--border-radius);
    border: 1px solid var(--gray-200);
    display: none;
}

.image-preview.show {
    display: block;
}

/* Flash Messages */
.flash-container {
    position: fixed;
    top: 80px;
    right: 20px;
    z-index:  1050;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 400px;
}

.flash {
    padding: 1rem 1.5rem;
    border-radius: var(--border-radius);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    animation: slideIn 0.3s ease;
    box-shadow: var(--shadow-lg);
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

. flash-success {
    background: var(--success-light);
    color: #155724;
    border-left: 4px solid var(--success);
}

.flash-error {
    background: var(--danger-light);
    color: #721c24;
    border-left: 4px solid var(--danger);
}

.flash-warning {
    background: var(--warning-light);
    color: #856404;
    border-left: 4px solid var(--warning);
}

.flash-info {
    background: var(--info-light);
    color: #0c5460;
    border-left: 4px solid var(--info);
}

.flash-close {
    background: none;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    opacity: 0.5;
    transition: var(--transition);
}

.flash-close:hover {
    opacity:  1;
}

/* Login Page */
.login-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    background: linear-gradient(135deg, var(--secondary) 0%, var(--primary-dark) 100%);
}

.login-card {
    background: var(--white);
    border-radius: var(--border-radius);
    box-shadow: var(--shadow-lg);
    padding: 3rem;
    width: 100%;
    max-width: 400px;
    text-align: center;
}

.login-logo {
    width: 150px;
    margin-bottom: 1.5rem;
}

.login-title {
    color: var(--secondary);
    margin-bottom: 0.5rem;
}

.login-subtitle {
    color: var(--gray-600);
    margin-bottom: 2rem;
}

/* Dashboard */
.dashboard-header {
    margin-bottom: 2rem;
}

.config-status {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: var(--border-radius);
    margin-bottom:  1.5rem;
}

.config-status.configured {
    background: var(--success-light);
    color: #155724;
}

.config-status.not-configured {
    background: var(--warning-light);
    color: #856404;
}

.config-status-icon {
    font-size:  1.5rem;
}

.mode-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
    margin-top: 1.5rem;
}

.mode-card {
    background: var(--white);
    border-radius: var(--border-radius);
    padding: 2rem;
    text-align: center;
    box-shadow: var(--shadow);
    transition: var(--transition);
    cursor: pointer;
    text-decoration: none;
    color: inherit;
    border: 2px solid transparent;
}

.mode-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--shadow-lg);
    border-color: var(--primary);
    text-decoration: none;
}

.mode-card-icon {
    font-size: 3rem;
    color: var(--primary);
    margin-bottom: 1rem;
}

.mode-card-title {
    color: var(--secondary);
    margin-bottom: 0.5rem;
}

.mode-card-description {
    color:  var(--gray-600);
    font-size: 0.875rem;
}

.mode-card. disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
}

/* Loading States */
.loading {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--gray-300);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

. btn . spinner {
    width: 16px;
    height: 16px;
    border-width: 2px;
    border-top-color: currentColor;
}

/* Results Section */
.results-section {
    text-align: center;
    padding: 3rem;
}

.results-icon {
    font-size: 4rem;
    color: var(--success);
    margin-bottom: 1rem;
}

/* Footer */
.footer {
    background: var(--gray-100);
    padding: 1.5rem;
    text-align: center;
    color: var(--gray-600);
    font-size: 0.875rem;
    border-top: 1px solid var(--gray-200);
}

/* Utilities */
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-muted { color: var(--gray-600); }
.text-success { color: var(--success); }
.text-danger { color: var(--danger); }
.text-warning { color: var(--warning); }

. mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mt-3 { margin-top: 1.5rem; }
.mt-4 { margin-top:  2rem; }
.mb-1 { margin-bottom:  0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-3 { margin-bottom: 1.5rem; }
.mb-4 { margin-bottom:  2rem; }

.hidden { display: none ! important; }

/* Responsive */
@media (max-width:  768px) {
    .navbar {
        flex-wrap: wrap;
        padding: 1rem;
    }
    
    .navbar-nav {
        order: 3;
        width: 100%;
        flex-direction: column;
        gap: 0.5rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255,255,255,0.1);
        margin-top: 1rem;
    }
    
    main {
        padding: 1rem;
    }
    
    .form-row {
        grid-template-columns: 1fr;
    }
    
    .login-card {
        padding: 2rem;
    }
}
```

### 26. `web/static/js/app.js`

Create main JavaScript file:

```javascript
/**
 * ASET Marking System - Main JavaScript
 */

// Flash Messages
class FlashManager {
    constructor() {
        this.container = document.getElementById('flash-container');
        this.autoHideDelay = 5000;
    }

    show(message, type = 'info') {
        const flash = document.createElement('div');
        flash.className = `flash flash-${type}`;
        flash.innerHTML = `
            <span>${message}</span>
            <button class="flash-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        if (this.container) {
            this. container.appendChild(flash);
            
            // Auto-hide after delay
            setTimeout(() => {
                flash.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => flash.remove(), 300);
            }, this.autoHideDelay);
        }
    }

    success(message) { this.show(message, 'success'); }
    error(message) { this.show(message, 'error'); }
    warning(message) { this.show(message, 'warning'); }
    info(message) { this.show(message, 'info'); }
}

const flash = new FlashManager();

// File Input Handler
class FileInputHandler {
    constructor(inputElement, previewElement = null) {
        this.input = inputElement;
        this. preview = previewElement;
        this.wrapper = inputElement.closest('.file-input-wrapper');
        
        if (this.input) {
            this.input.addEventListener('change', (e) => this.handleChange(e));
        }
    }

    handleChange(e) {
        const file = e. target.files[0];
        if (! file) return;

        // Update wrapper text
        if (this.wrapper) {
            const nameEl = this.wrapper.querySelector('.file-name');
            if (nameEl) {
                nameEl.textContent = file.name;
            } else {
                const newName = document.createElement('div');
                newName.className = 'file-name';
                newName.textContent = file. name;
                this.wrapper. appendChild(newName);
            }
        }

        // Show image preview if applicable
        if (this.preview && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.preview. src = e.target.result;
                this.preview.classList. add('show');
            };
            reader.readAsDataURL(file);
        }
    }
}

// Form Handler with Loading State
class FormHandler {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.submitBtn = formElement.querySelector('[type="submit"]');
        this.options = {
            onSuccess: options.onSuccess || (() => {}),
            onError: options. onError || ((err) => flash.error(err)),
            resetOnSuccess: options.resetOnSuccess !== false,
            downloadResponse: options.downloadResponse || false,
            ...options
        };

        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    }

    setLoading(loading) {
        if (!this.submitBtn) return;

        if (loading) {
            this. submitBtn.disabled = true;
            this.originalText = this.submitBtn.innerHTML;
            this.submitBtn. innerHTML = `<span class="spinner"></span> Processing...`;
        } else {
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = this.originalText;
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        this.setLoading(true);

        try {
            const formData = new FormData(this.form);
            const response = await fetch(this.form. action, {
                method: 'POST',
                body: formData
            });

            if (this.options.downloadResponse) {
                if (response.ok) {
                    const blob = await response.blob();
                    const contentDisposition = response.headers.get('Content-Disposition');
                    let filename = 'download. zip';
                    
                    if (contentDisposition) {
                        const match = contentDisposition.match(/filename=(. +)/);
                        if (match) filename = match[1]. replace(/"/g, '');
                    }

                    // Trigger download
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window. URL.revokeObjectURL(url);

                    this.options.onSuccess(response);
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || 'Processing failed');
                }
            } else {
                const data = await response.json();
                
                if (response.ok) {
                    this.options.onSuccess(data);
                    if (this.options.resetOnSuccess) {
                        this.form.reset();
                    }
                } else {
                    throw new Error(data.detail || 'Request failed');
                }
            }
        } catch (error) {
            this.options.onError(error. message);
        } finally {
            this.setLoading(false);
        }
    }
}

// Configuration Form Handler
function initConfigurationForm() {
    const form = document.getElementById('config-form');
    if (!form) return;

    new FormHandler(form, {
        onSuccess: (data) => {
            flash.success('Configuration loaded successfully!');
            updateConfigStatus(data.summary);
            enableMarkingModes();
        },
        onError:  (err) => {
            flash.error(`Configuration error: ${err}`);
        },
        resetOnSuccess: false
    });
}

function updateConfigStatus(summary) {
    const statusEl = document.getElementById('config-status');
    if (!statusEl) return;

    statusEl.className = 'config-status configured';
    statusEl.innerHTML = `
        <span class="config-status-icon">✓</span>
        <div>
            <strong>Configuration Loaded</strong>
            <div class="text-muted">
                Reading:  ${summary.reading_questions} questions | 
                QR/AR: ${summary.qrar_questions} questions |
                Subjects: ${summary.subjects_mapped. join(', ')}
            </div>
        </div>
    `;
}

function enableMarkingModes() {
    document.querySelectorAll('.mode-card. disabled').forEach(card => {
        card.classList.remove('disabled');
    });
}

// Single Marking Form Handler
function initSingleMarkingForm() {
    const form = document.getElementById('marking-form');
    if (!form) return;

    // Initialize file inputs with previews
    document.querySelectorAll('.file-input-wrapper input[type="file"]').forEach(input => {
        const previewId = input.dataset.preview;
        const preview = previewId ? document.getElementById(previewId) : null;
        new FileInputHandler(input, preview);
    });

    new FormHandler(form, {
        downloadResponse: true,
        onSuccess: () => {
            flash.success('Marking complete! Download started.');
            document.getElementById('marking-form-container').classList.add('hidden');
            document.getElementById('results-section').classList.remove('hidden');
        },
        onError: (err) => {
            flash.error(`Marking failed: ${err}`);
        }
    });
}

// Batch Form Handler
function initBatchForm() {
    const form = document. getElementById('batch-form');
    if (!form) return;

    document.querySelectorAll('.file-input-wrapper input[type="file"]').forEach(input => {
        new FileInputHandler(input);
    });

    new FormHandler(form, {
        downloadResponse: true,
        onSuccess: () => {
            flash. success('Batch processing complete! Download started.');
            document.getElementById('batch-form-container').classList.add('hidden');
            document. getElementById('results-section').classList.remove('hidden');
        },
        onError: (err) => {
            flash.error(`Batch processing failed: ${err}`);
        }
    });
}

// Reset form and show it again
function resetAndShowForm(formContainerId, resultsSectionId) {
    const form = document.querySelector(`#${formContainerId} form`);
    if (form) form.reset();
    
    document.getElementById(formContainerId).classList.remove('hidden');
    document.getElementById(resultsSectionId).classList.add('hidden');
    
    // Clear file previews
    document.querySelectorAll('.image-preview').forEach(preview => {
        preview.classList.remove('show');
        preview.src = '';
    });
    
    document.querySelectorAll('.file-name').forEach(el => el.remove());
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    initConfigurationForm();
    initSingleMarkingForm();
    initBatchForm();

    // Initialize any standalone file inputs
    document.querySelectorAll('.file-input-wrapper input[type="file"]').forEach(input => {
        if (! input._handler) {
            input._handler = new FileInputHandler(input);
        }
    });
});
```

### 27. `docs/sample_answer_key.txt`

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

### 28. `docs/sample_answer_key. csv`

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

### 29. `docs/sample_concept_mapping.json`

```json
{
    "_instructions": "This file maps questions to learning areas.  Edit to match your exam.",
    "_threshold": "Students scoring ≥51% in an area are 'Done Well', below 51% is 'Needs Improvement'",
    "_format": "Each question should appear in exactly ONE area per subject",
    
    "Reading":  {
        "Main Idea & Theme": ["q1", "q6", "q11", "q16", "q21", "q26"],
        "Inference & Interpretation": ["q2", "q7", "q12", "q17", "q22", "q27"],
        "Vocabulary in Context": ["q3", "q8", "q13", "q18", "q23", "q28"],
        "Author's Purpose & Tone": ["q4", "q9", "q14", "q19", "q24", "q29"],
        "Text Structure & Features": ["q5", "q10", "q15", "q20", "q25", "q30"]
    },
    
    "Quantitative Reasoning": {
        "Number & Operations": ["qr1", "qr2", "qr3", "qr4", "qr5"],
        "Algebra & Patterns": ["qr6", "qr7", "qr8", "qr9", "qr10"],
        "Measurement":  ["qr11", "qr12", "qr13", "qr14", "qr15"],
        "Geometry & Spatial Sense": ["qr16", "qr17", "qr18", "qr19", "qr20"],
        "Statistics & Probability": ["qr21", "qr22", "qr23", "qr24", "qr25"]
    },
    
    "Abstract Reasoning": {
        "Pattern Recognition": ["ar1", "ar2", "ar3", "ar4", "ar5", "ar6", "ar7"],
        "Spatial Reasoning": ["ar8", "ar9", "ar10", "ar11", "ar12", "ar13"],
        "Logical Sequences": ["ar14", "ar15", "ar16", "ar17", "ar18", "ar19", "ar20"]
    }
}
```

### 30. `tests/conftest.py`

```python
"""Pytest configuration and fixtures."""
import pytest
from fastapi.testclient import TestClient

from web.app import app
from web.auth import create_session, STAFF_PASSWORD_HASH
from web.session_store import config_store, MarkingConfiguration


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client."""
    # Login first
    response = client.post("/login", data={"password": "everest2024"})
    return client


@pytest.fixture
def configured_client(authenticated_client):
    """Create authenticated and configured test client."""
    # Get session token from cookies
    session_token = authenticated_client.cookies. get("session_token")
    
    # Set up configuration
    config = MarkingConfiguration(
        reading_answers=["A", "B", "C", "D"] * 8,  # 32 answers
        qrar_answers=["A", "B", "C", "D", "E"] * 9,  # 45 answers
        concept_mapping={
            "Reading": {"Area1": ["q1", "q2"], "Area2": ["q3", "q4"]},
            "Quantitative Reasoning": {"Area1": ["qr1", "qr2"]},
            "Abstract Reasoning":  {"Area1": ["ar1", "ar2"]}
        }
    )
    config_store.set(session_token, config)
    
    return authenticated_client


@pytest.fixture
def sample_png_bytes():
    """Create minimal valid PNG bytes for testing."""
    # Minimal 1x1 white PNG
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])
```

### 31. `tests/test_auth.py`

```python
"""Authentication tests."""
import pytest
from web.auth import verify_password, create_session, validate_session, invalidate_session


def test_verify_password_correct():
    """Test correct password verification."""
    assert verify_password("everest2024") is True


def test_verify_password_incorrect():
    """Test incorrect password rejection."""
    assert verify_password("wrongpassword") is False
    assert verify_password("") is False


def test_session_lifecycle():
    """Test session creation, validation, and invalidation."""
    token = create_session()
    
    assert token is not None
    assert len(token) > 20
    assert validate_session(token) is True
    
    invalidate_session(token)
    assert validate_session(token) is False


def test_invalid_session():
    """Test invalid session token."""
    assert validate_session("invalid-token") is False
    assert validate_session("") is False


def test_login_page_renders(client):
    """Test login page renders correctly."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.content or b"login" in response.content


def test_login_success(client):
    """Test successful login."""
    response = client.post(
        "/login",
        data={"password": "everest2024"},
        follow_redirects=False
    )
    assert response.status_code in [302, 303]
    assert "session_token" in response.cookies