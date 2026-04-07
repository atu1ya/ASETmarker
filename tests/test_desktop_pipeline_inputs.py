from __future__ import annotations

from pathlib import Path

import pytest

from desktop.pipeline import DesktopBatchProcessor, EXPECTED_CSV_HEADERS, QUESTIONS_PER_SUBJECT


@pytest.fixture
def processor() -> DesktopBatchProcessor:
    # Bypass heavy __init__ dependencies; these parser methods are self-contained.
    return DesktopBatchProcessor.__new__(DesktopBatchProcessor)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(item) for item in row))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_load_students_csv_uses_writing_percent_column(tmp_path: Path, processor: DesktopBatchProcessor) -> None:
    csv_path = tmp_path / "students.csv"
    row = [
        "Alice Smith",  # STUDENT NAME
        "22",  # Reading Score (/35)
        "62.9",  # Reading %
        "70",  # Standardised Reading Score
        "25",  # QR Score (/35)
        "71.4",  # QR %
        "72",  # Standardised QR Score
        "20",  # AR score (/35)
        "57.1",  # AR %
        "66",  # Standardised AR Score
        "44",  # Writing Score (/50)
        "88.0",  # Writing % <- must be used
        "75",  # Standardised Writing Score
        "283",  # Total Standard Score (/400)
        "111",  # Total Score BEFORE standardising
    ]
    _write_csv(csv_path, EXPECTED_CSV_HEADERS, [row])

    students = processor.load_students_csv(csv_path)

    assert len(students) == 1
    assert students[0].name == "Alice Smith"
    assert students[0].writing_percent == 88.0


def test_load_students_csv_requires_expected_headers(tmp_path: Path, processor: DesktopBatchProcessor) -> None:
    csv_path = tmp_path / "students_missing_headers.csv"
    bad_headers = EXPECTED_CSV_HEADERS[:-1]
    _write_csv(csv_path, bad_headers, [["Bob"] * len(bad_headers)])

    with pytest.raises(ValueError, match="missing expected headers"):
        processor.load_students_csv(csv_path)


def test_load_answer_key_unlabeled_mode_supports_105_answers(
    tmp_path: Path,
    processor: DesktopBatchProcessor,
) -> None:
    answers = ["ABCDE"[idx % 5] for idx in range(QUESTIONS_PER_SUBJECT * 3)]
    answer_key_path = tmp_path / "answer_key.txt"
    answer_key_path.write_text("\n".join(answers), encoding="utf-8")

    bundle = processor._load_answer_key(answer_key_path)

    assert len(bundle.reading) == QUESTIONS_PER_SUBJECT
    assert len(bundle.qr) == QUESTIONS_PER_SUBJECT
    assert len(bundle.ar) == QUESTIONS_PER_SUBJECT
    assert bundle.reading[0] == "A"
    assert bundle.qr[0] == answers[QUESTIONS_PER_SUBJECT]
    assert bundle.ar[-1] == answers[-1]


def test_load_answer_key_rejects_mixed_formats(tmp_path: Path, processor: DesktopBatchProcessor) -> None:
    answer_key_path = tmp_path / "mixed_answer_key.txt"
    answer_key_path.write_text("RC1 A\nA\n", encoding="utf-8")

    with pytest.raises(ValueError, match="cannot mix labeled rows"):
        processor._load_answer_key(answer_key_path)


def test_load_answer_key_csv_with_header_and_labeled_rows(
    tmp_path: Path,
    processor: DesktopBatchProcessor,
) -> None:
    rows = ["Question,Answer"]
    for idx in range(1, QUESTIONS_PER_SUBJECT + 1):
        rows.append(f"RC{idx},A")
    for idx in range(1, QUESTIONS_PER_SUBJECT + 1):
        rows.append(f"QR{idx},B")
    for idx in range(1, QUESTIONS_PER_SUBJECT + 1):
        rows.append(f"AR{idx},C")

    answer_key_path = tmp_path / "answer_key.csv"
    answer_key_path.write_text("\n".join(rows), encoding="utf-8")

    bundle = processor._load_answer_key(answer_key_path)

    assert bundle.reading == ["A"] * QUESTIONS_PER_SUBJECT
    assert bundle.qr == ["B"] * QUESTIONS_PER_SUBJECT
    assert bundle.ar == ["C"] * QUESTIONS_PER_SUBJECT


def test_load_answer_key_csv_single_answer_column_with_header(
    tmp_path: Path,
    processor: DesktopBatchProcessor,
) -> None:
    answers = ["ABCDE"[idx % 5] for idx in range(QUESTIONS_PER_SUBJECT * 3)]
    answer_key_path = tmp_path / "answer_key_single_col.csv"
    answer_key_path.write_text("Answer\n" + "\n".join(answers), encoding="utf-8")

    bundle = processor._load_answer_key(answer_key_path)

    assert bundle.reading[0] == answers[0]
    assert bundle.qr[0] == answers[QUESTIONS_PER_SUBJECT]
    assert bundle.ar[-1] == answers[-1]


def test_load_single_subject_answer_key_csv_q_prefixed_labels(
    tmp_path: Path,
    processor: DesktopBatchProcessor,
) -> None:
    rows = ["Question,Answer"]
    for idx in range(1, QUESTIONS_PER_SUBJECT + 1):
        rows.append(f"q{idx},A")

    answer_key_path = tmp_path / "reading_key.csv"
    answer_key_path.write_text("\n".join(rows), encoding="utf-8")

    reading_answers = processor._load_single_subject_answer_key(answer_key_path, "reading")

    assert len(reading_answers) == QUESTIONS_PER_SUBJECT
    assert reading_answers == ["A"] * QUESTIONS_PER_SUBJECT


def test_load_single_subject_answer_key_txt_unlabeled_35_answers(
    tmp_path: Path,
    processor: DesktopBatchProcessor,
) -> None:
    answers = ["ABCDE"[idx % 5] for idx in range(QUESTIONS_PER_SUBJECT)]
    answer_key_path = tmp_path / "ar_key.txt"
    answer_key_path.write_text("\n".join(answers), encoding="utf-8")

    ar_answers = processor._load_single_subject_answer_key(answer_key_path, "ar")

    assert ar_answers == answers


def test_missing_writing_placeholder_pdf_is_generated(processor: DesktopBatchProcessor) -> None:
    fitz = pytest.importorskip("fitz")

    pdf_bytes = processor._create_missing_writing_pdf(
        student_name="Alice Smith",
        source_doc=Path("alice.pdf"),
        page_count=2,
    )

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        assert doc.page_count == 1
    finally:
        doc.close()


def test_load_concept_mapping_accepts_aliases(tmp_path: Path, processor: DesktopBatchProcessor) -> None:
    concept_path = tmp_path / "concepts.json"
    concept_path.write_text(
        """
        {
          "Reading": {
            "Main ideas": ["r1", "r2"]
          },
          "QR": {
            "Algebra": ["qr1", "qr2"]
          },
          "AR": {
            "Patterns": ["ar1"]
          }
        }
        """,
        encoding="utf-8",
    )

    mapping = processor._load_concept_mapping(concept_path)

    assert "Main ideas" in mapping["Reading"]
    assert "Algebra" in mapping["Quantitative Reasoning"]
    assert "Patterns" in mapping["Abstract Reasoning"]
