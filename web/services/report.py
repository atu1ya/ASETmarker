"""
PDF report generation service.
STUB IMPLEMENTATION - Full implementation in Milestone 3.
"""
from pathlib import Path


class ReportService:
    """Generates branded PDF reports for students."""

    def __init__(self, assets_dir: Path):
        self.assets_dir = assets_dir
        self.logo_path = assets_dir / "everest_logo.png"

    def generate_student_report(
        self,
        student_name: str,
        reading_score: dict,
        qr_score: dict,
        ar_score: dict,
        writing_score: int,
        analysis: dict,
    ) -> bytes:
        """
        Generate a complete student report PDF.

        STUB: Returns a minimal valid PDF for testing.
        """
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
