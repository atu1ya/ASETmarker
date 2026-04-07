from __future__ import annotations

from pathlib import Path

import pytest

from desktop.io.merged_document_splitter import MergedDocumentSplitter


@pytest.fixture
def fitz_module():
    return pytest.importorskip("fitz")


def _create_pdf(path: Path, page_count: int, fitz_module) -> None:
    doc = fitz_module.open()
    for index in range(page_count):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {index + 1}")
    doc.save(str(path))
    doc.close()


def test_splitter_accepts_two_pages_without_writing(tmp_path: Path, fitz_module) -> None:
    pdf_path = tmp_path / "student_two_pages.pdf"
    _create_pdf(pdf_path, page_count=2, fitz_module=fitz_module)

    splitter = MergedDocumentSplitter()
    result = splitter.split_document(pdf_path)

    assert result.page_count == 2
    assert result.reading_page_gray is not None
    assert result.qrar_page_gray is not None
    assert result.writing_page_gray is None
    assert result.writing_page_pdf is None
    assert result.warnings


def test_splitter_exports_writing_pages_for_three_plus_pages(tmp_path: Path, fitz_module) -> None:
    pdf_path = tmp_path / "student_four_pages.pdf"
    _create_pdf(pdf_path, page_count=4, fitz_module=fitz_module)

    splitter = MergedDocumentSplitter()
    result = splitter.split_document(pdf_path)

    assert result.page_count == 4
    assert result.writing_page_gray is not None
    assert result.writing_page_pdf is not None
    assert not result.warnings

    writing_pdf = fitz_module.open(stream=result.writing_page_pdf, filetype="pdf")
    try:
        # Writing export includes pages 3+ from source document.
        assert writing_pdf.page_count == 2
    finally:
        writing_pdf.close()
