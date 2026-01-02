"""
Annotated sheet generation service.
STUB IMPLEMENTATION - Full implementation in Milestone 3.
"""
import numpy as np


class AnnotatorService:
    """Generates annotated marked sheets highlighting correct/incorrect answers."""

    INCORRECT_COLOR = (0, 0, 255)  # Red in BGR
    CORRECT_COLOR = (0, 255, 0)  # Green in BGR

    def annotate_sheet(
        self,
        marked_image: np.ndarray,
        question_results: list[dict],
        subject: str,
        score: dict,
    ) -> np.ndarray:
        """
        Annotate a marked sheet with visual indicators.

        STUB: Returns the image as-is.
        """
        return marked_image

    def image_to_pdf_bytes(self, image: np.ndarray) -> bytes:
        """Convert image to PDF bytes.

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
