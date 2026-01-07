ASET Marking System - Milestone 3: PDF Reporting & Annotation
Context
We have completed M2 (Core Marking Service), which outputs structured results (SubjectResult) and analysis (FullAnalysis). Now we must implement Milestone 3 (M3): Generating the downloadable artifacts.

Goal: Implement the services that produce:

Annotated Marked Sheets: The original OMR scan converted to PDF, with the score overlaid.

Student Report: A professional, branded PDF summarizing performance, strengths, and weaknesses.

Constraints:

Use reportlab for PDF generation.

Use cv2 (OpenCV) and PIL (Pillow) for image manipulation.

Branding Colors: Primary: #3498DB (Blue), Secondary: #2C3E50 (Dark Blue/Grey).

Output: All functions must return raw bytes (ready for ZIP bundling), not file paths.

Reference: Input Data Structures (from M2)
Assume these dataclasses exist in web.services.marker and web.services.analysis. You will process instances of these classes.

Python

@dataclass
class SubjectResult:
    subject_name: str    # "Reading" or "QR/AR"
    score: int
    total_questions: int
    results: List[QuestionResult] # (label, marked_value, correct_value, is_correct)
    marked_image: Any    # cv2 numpy array (BGR)

@dataclass
class LearningAreaResult:
    area_name: str
    percentage: float
    status: str          # "Done well" or "Needs improvement"

@dataclass
class FullAnalysis:
    student_name: str
    writing_score: int
    reading_analysis: List[LearningAreaResult]
    qrar_analysis: List[LearningAreaResult]
    reading_total_score: int
    qrar_total_score: int
    reading_max_score: int
    qrar_max_score: int
Detailed File Specifications
1. web/services/annotator.py
Responsibilities:

annotate_sheet(subject_result: SubjectResult) -> bytes:

Take the marked_image (numpy array) from the result.

Overlay Score: Draw a clear, large text box at the top-left or top-right of the image displaying the score (e.g., "Score: 25/30"). Use cv2.putText with a white background rectangle for readability.

Convert to PDF: Convert the modified BGR numpy array to a PDF byte stream.

Hint: Use cv2.cvtColor (BGR to RGB) -> PIL.Image.fromarray -> img.save(buffer, format="PDF").

Implementation Skeleton:

Python

import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from web.services.marker import SubjectResult

class AnnotatorService:
    def annotate_sheet(self, result: SubjectResult) -> bytes:
        # 1. Get image copy
        img = result.marked_image.copy()
        
        # 2. Overlay Score
        text = f"Score: {result.score} / {result.total_questions}"
        # (Add logic here to draw a filled rectangle and putText on top)
        
        # 3. Convert to PDF Bytes
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        buffer = BytesIO()
        pil_img.save(buffer, format="PDF")
        return buffer.getvalue()
2. web/services/report.py
Responsibilities:

generate_student_report(analysis: FullAnalysis) -> bytes:

Use reportlab.platypus (SimpleDocTemplate, Paragraph, Table, Spacer) for a professional layout.

Header: Title "Student Performance Report", Student Name, Date.

Summary Section: A table showing scores for Reading, QR/AR, Writing, and Total.

Detailed Analysis:

Create a function to generate a styled table for a list of LearningAreaResult.

Columns: "Learning Area", "Performance", "Status".

Conditional Formatting: Text color for "Done well" (Green) vs "Needs improvement" (Red/Orange).

Branding: Use the defined colors (#3498DB, #2C3E50) for headers and table borders.

Implementation Skeleton:

Python

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from web.services.analysis import FullAnalysis

class ReportService:
    def generate_student_report(self, analysis: FullAnalysis) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Define Custom Styles (Brand Colors)
        # title_style = ...
        # header_style = ...

        # 1. Header (Name, Date)
        
        # 2. Score Summary Table
        # Data: [['Subject', 'Score', 'Max'], ['Reading', ..., ...], ...]
        
        # 3. Reading Analysis Section
        # Title: "Reading Analysis"
        # Table: Area | % | Status
        
        # 4. QR/AR Analysis Section
        
        doc.build(elements)
        return buffer.getvalue()
3. web/services/__init__.py
Update the exports to include the new services.

Python

# ... (Previous exports)
from web.services.report import ReportService
from web.services.annotator import AnnotatorService

__all__ = [
    # ... (Previous exports)
    "ReportService",
    "AnnotatorService"
]
Task: Generate the full code for:

web/services/annotator.py

web/services/report.py

web/services/__init__.py (Updated)

Ensure the code handles potential edge cases (e.g., empty analysis lists) and produces professional-looking PDFs.