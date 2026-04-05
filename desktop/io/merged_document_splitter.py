from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image, ImageSequence

SUPPORTED_MERGED_EXTENSIONS = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}


def _pdf_to_pages(doc_path: Path) -> List[np.ndarray]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PDF input requires PyMuPDF (`pip install pymupdf`).") from exc

    pages: List[np.ndarray] = []
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


def _tiff_to_pages(doc_path: Path) -> List[np.ndarray]:
    pages: List[np.ndarray] = []
    with Image.open(doc_path) as tif:
        for frame in ImageSequence.Iterator(tif):
            pages.append(np.array(frame.convert("L")))
    return pages


def _single_image_to_page(doc_path: Path) -> List[np.ndarray]:
    image = cv2.imread(str(doc_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not decode image: {doc_path}")
    return [image]


def extract_merged_document_pages(doc_path: Path) -> List[np.ndarray]:
    suffix = doc_path.suffix.lower()
    if suffix not in SUPPORTED_MERGED_EXTENSIONS:
        raise ValueError(f"Unsupported merged scan format: {doc_path}")

    if suffix in {".png", ".jpg", ".jpeg"}:
        return _single_image_to_page(doc_path)
    if suffix in {".tif", ".tiff"}:
        return _tiff_to_pages(doc_path)
    return _pdf_to_pages(doc_path)
