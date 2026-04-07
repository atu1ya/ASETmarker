from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image, ImageSequence


SUPPORTED_SCAN_EXTENSIONS = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}


@dataclass
class SplitDocumentPages:
    reading_page_gray: np.ndarray
    qrar_page_gray: np.ndarray
    writing_page_gray: Optional[np.ndarray]
    writing_page_pdf: Optional[bytes]
    page_count: int
    warnings: List[str]


class MergedDocumentSplitter:
    """Splits a merged student scan into Reading, QR/AR, and Writing pages."""

    def split_document(self, doc_path: Path) -> SplitDocumentPages:
        doc_path = Path(doc_path)
        suffix = doc_path.suffix.lower()
        if suffix not in SUPPORTED_SCAN_EXTENSIONS:
            raise ValueError(f"Unsupported scan file type: {doc_path}")

        pages = self._extract_pages_as_grayscale(doc_path)
        page_count = len(pages)
        if page_count < 2:
            raise ValueError(
                "Merged document must include at least 2 pages in this order: Reading, QR/AR, (optional) Writing."
            )

        reading_page = pages[0]
        qrar_page = pages[1]
        writing_page = pages[2] if page_count >= 3 else None
        warnings: List[str] = []

        writing_page_pdf: Optional[bytes]
        if page_count >= 3:
            if suffix == ".pdf":
                writing_page_pdf = self._extract_pdf_pages_from(pdf_path=doc_path, start_page=2)
            else:
                writing_page_pdf = self._images_to_pdf_bytes(pages[2:])
        else:
            writing_page_pdf = None
            warnings.append(
                "Writing page not found (only 2 pages supplied). A placeholder writing sheet will be generated."
            )

        return SplitDocumentPages(
            reading_page_gray=reading_page,
            qrar_page_gray=qrar_page,
            writing_page_gray=writing_page,
            writing_page_pdf=writing_page_pdf,
            page_count=page_count,
            warnings=warnings,
        )

    def _extract_pages_as_grayscale(self, doc_path: Path) -> List[np.ndarray]:
        suffix = doc_path.suffix.lower()

        if suffix in {".png", ".jpg", ".jpeg"}:
            image = cv2.imread(str(doc_path), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError(f"Could not decode image: {doc_path}")
            return [image]

        if suffix in {".tif", ".tiff"}:
            pages: List[np.ndarray] = []
            with Image.open(doc_path) as tif:
                for frame in ImageSequence.Iterator(tif):
                    pages.append(np.array(frame.convert("L")))
            return pages

        if suffix == ".pdf":
            try:
                import fitz  # type: ignore
            except ImportError as exc:
                raise RuntimeError("PDF input requires PyMuPDF (`pip install pymupdf`).") from exc

            pages = []
            with fitz.open(str(doc_path)) as pdf:
                for page in pdf:
                    pix = page.get_pixmap(dpi=220, alpha=False)
                    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                    if pix.n == 1:
                        gray = arr
                    else:
                        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                    pages.append(gray)
            return pages

        raise ValueError(f"Unsupported merged scan format: {doc_path}")

    @staticmethod
    def _extract_pdf_pages_from(pdf_path: Path, start_page: int) -> bytes:
        try:
            import fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PDF output requires PyMuPDF (`pip install pymupdf`).") from exc

        with fitz.open(str(pdf_path)) as source_pdf:
            if source_pdf.page_count <= start_page:
                raise ValueError(
                    f"Expected at least {start_page + 1} pages in merged PDF, found {source_pdf.page_count}."
                )

            output_pdf = fitz.open()
            output_pdf.insert_pdf(source_pdf, from_page=start_page, to_page=source_pdf.page_count - 1)
            try:
                return output_pdf.tobytes(garbage=4, deflate=True)
            finally:
                output_pdf.close()

    @staticmethod
    def _images_to_pdf_bytes(images: List[np.ndarray]) -> bytes:
        if not images:
            raise ValueError("Expected at least one writing image to convert to PDF.")

        pil_pages: List[Image.Image] = []
        for image in images:
            if image.ndim == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_page = Image.fromarray(rgb_image)
            else:
                pil_page = Image.fromarray(image)
            pil_pages.append(pil_page.convert("RGB"))

        from io import BytesIO

        buffer = BytesIO()
        first, *rest = pil_pages
        first.save(buffer, format="PDF", resolution=220.0, save_all=True, append_images=rest)
        return buffer.getvalue()
