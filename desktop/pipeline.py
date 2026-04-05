from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pandas as pd

from desktop.services import AnalysisService, AnnotatorService, DocxReportGenerator, MarkingService
from desktop.services.concept_loader import load_concepts
from desktop.services.marker import SubjectResult
from desktop.io.merged_document_splitter import extract_merged_document_pages


SUPPORTED_SCAN_EXTENSIONS = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}
SUPPORTED_ROSTER_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@dataclass
class StudentInput:
    name: str
    writing_score: float


@dataclass
class StudentRunResult:
    name: str
    status: str
    reading_score: float = 0.0
    qr_score: float = 0.0
    ar_score: float = 0.0
    notes: str = ""
    output_dir: Optional[Path] = None


@dataclass
class BatchRunSummary:
    output_dir: Path
    results: List[StudentRunResult]


@dataclass
class SingleRunSummary:
    output_dir: Path
    result: StudentRunResult


class DesktopBatchProcessor:
    def __init__(self, repo_root: Path, year_level: str = "year4_5"):
        self.repo_root = Path(repo_root)
        self.year_level = year_level
        self.config_dir = self.repo_root / "config"
        self.docs_dir = self.repo_root / "docs"

        self.marking_service = MarkingService(self.config_dir)
        self.annotator = AnnotatorService()

        concept_config = load_concepts(year_level)
        self.concept_mapping = {
            key: value
            for key, value in concept_config.items()
            if isinstance(value, dict)
            and key in {"Reading", "Quantitative Reasoning", "Abstract Reasoning"}
        }

        self.analysis_service = AnalysisService(self.concept_mapping)
        self.docx_generator = DocxReportGenerator(year_level=year_level)

        self.reading_answers = self._load_answer_key(self.docs_dir / "reading_answer_key.csv")
        self.qr_answers = self._load_answer_key(self.docs_dir / "qr_answer_key.csv")
        self.ar_answers = self._load_answer_key(self.docs_dir / "ar_answer_key.csv")

    @staticmethod
    def _normalize_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def _load_answer_key(self, path: Path) -> List[str]:
        if not path.exists():
            raise FileNotFoundError(f"Answer key file not found: {path}")

        answers: List[str] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row:
                    continue
                answer = row[-1].strip()
                if not answer:
                    continue
                answers.append(answer)
        if not answers:
            raise ValueError(f"Answer key is empty: {path}")
        return answers

    def load_students_sheet(self, sheet_path: Path) -> List[StudentInput]:
        suffix = sheet_path.suffix.lower()
        if suffix not in SUPPORTED_ROSTER_EXTENSIONS:
            raise ValueError(
                "Roster must be a CSV or Excel file (.csv, .xlsx, .xls)."
            )

        if suffix == ".csv":
            frame = pd.read_csv(sheet_path, encoding="utf-8-sig")
        else:
            frame = pd.read_excel(sheet_path)

        if frame.empty:
            raise ValueError("Roster file does not contain any rows.")

        headers = [str(c) for c in frame.columns]
        name_col = self._find_column(headers, ["student name", "name", "student"])
        writing_col = self._find_column(headers, ["writing score", "writing", "writing_score"])
        if not name_col or not writing_col:
            raise ValueError(
                "Roster must include name and writing score columns (for example: 'Student Name' and 'Writing Score')."
            )

        students: List[StudentInput] = []
        for _, row in frame.iterrows():
            raw_name = str(row.get(name_col, "")).strip()
            if not raw_name or raw_name.lower() == "nan":
                continue

            raw_writing = row.get(writing_col, None)
            if raw_writing is None or str(raw_writing).strip() == "":
                raise ValueError(f"Missing writing score for student: {raw_name}")

            try:
                writing_score = float(raw_writing)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid writing score '{raw_writing}' for student: {raw_name}") from exc

            students.append(StudentInput(name=raw_name, writing_score=writing_score))

        if not students:
            raise ValueError("Roster did not contain any valid student rows.")
        return students

    @staticmethod
    def _find_column(headers: Sequence[str], aliases: List[str]) -> Optional[str]:
        normalized = {str(h): str(h).strip().lower() for h in headers}
        for alias in aliases:
            for original, lowered in normalized.items():
                if lowered == alias or alias in lowered:
                    return original
        return None

    def _collect_merged_docs(self, scans_path: Path) -> List[Path]:
        if scans_path.is_file():
            if scans_path.suffix.lower() not in SUPPORTED_SCAN_EXTENSIONS:
                raise ValueError(f"Unsupported scan file type: {scans_path}")
            return [scans_path]

        if not scans_path.is_dir():
            raise FileNotFoundError(f"Scan path does not exist: {scans_path}")

        files = [
            p
            for p in scans_path.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_SCAN_EXTENSIONS
        ]
        if not files:
            raise ValueError(f"No scan files found in: {scans_path}")
        return sorted(files)

    def _map_students_to_docs(self, students: List[StudentInput], docs: List[Path]) -> Dict[str, Path]:
        if len(docs) == 1 and len(students) == 1:
            return {students[0].name: docs[0]}

        available = {doc: self._normalize_name(doc.stem) for doc in docs}
        mapping: Dict[str, Path] = {}

        for student in students:
            target = self._normalize_name(student.name)
            candidates = [doc for doc, stem in available.items() if stem == target]
            if not candidates:
                candidates = [doc for doc, stem in available.items() if target in stem or stem in target]

            if len(candidates) != 1:
                raise ValueError(
                    f"Could not uniquely match merged scan for student '{student.name}'. "
                    f"Ensure file names align with student names in CSV."
                )

            mapping[student.name] = candidates[0]

        return mapping

    def _extract_pages(self, doc_path: Path) -> List[np.ndarray]:
        return extract_merged_document_pages(doc_path)

    def _extract_three_pages(self, doc_path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        pages = self._extract_pages(doc_path)
        if len(pages) != 3:
            raise ValueError(
                "Merged document must contain exactly 3 pages in this order: "
                "Page 1 Reading, Page 2 QR/AR, Page 3 Writing."
            )
        return pages[0], pages[1], pages[2]

    @staticmethod
    def _encode_png_bytes(img: np.ndarray) -> bytes:
        ok, encoded = cv2.imencode(".png", img)
        if not ok:
            raise ValueError("Could not encode page image for marking.")
        return encoded.tobytes()

    def _split_qr_ar_result(self, qrar_result: SubjectResult) -> Tuple[SubjectResult, SubjectResult]:
        qr_len = len(self.qr_answers)
        ar_len = len(self.ar_answers)

        qr_results = qrar_result.results[:qr_len]
        ar_results = qrar_result.results[qr_len : qr_len + ar_len]

        qr_score = sum(1 for q in qr_results if q.is_correct)
        ar_score = sum(1 for q in ar_results if q.is_correct)

        qr = SubjectResult(
            subject_name="Quantitative Reasoning",
            score=qr_score,
            total_questions=qr_len,
            results=qr_results,
            omr_response=qrar_result.omr_response,
            marked_image=qrar_result.marked_image,
            template=qrar_result.template,
            clean_image=getattr(qrar_result, "clean_image", None),
        )
        ar = SubjectResult(
            subject_name="Abstract Reasoning",
            score=ar_score,
            total_questions=ar_len,
            results=ar_results,
            omr_response=qrar_result.omr_response,
            marked_image=qrar_result.marked_image,
            template=qrar_result.template,
            clean_image=getattr(qrar_result, "clean_image", None),
        )
        return qr, ar

    def _process_student_document(
        self,
        student: StudentInput,
        doc_path: Path,
        student_output_dir: Path,
    ) -> StudentRunResult:
        reading_page, qrar_page, writing_page = self._extract_three_pages(doc_path)

        reading_bytes = self._encode_png_bytes(reading_page)
        qrar_bytes = self._encode_png_bytes(qrar_page)

        reading_key = {f"RC{i+1}": ans for i, ans in enumerate(self.reading_answers)}
        qrar_key: Dict[str, str] = {}
        for i, ans in enumerate(self.qr_answers):
            qrar_key[f"QR{i+1}"] = ans
        for i, ans in enumerate(self.ar_answers):
            qrar_key[f"AR{i+1}"] = ans

        reading_result = self.marking_service.process_single_subject(
            subject_name="Reading",
            image_bytes=reading_bytes,
            answer_key=reading_key,
            template_filename="aset_reading_template.json",
        )
        qrar_result = self.marking_service.process_single_subject(
            subject_name="QR/AR",
            image_bytes=qrar_bytes,
            answer_key=qrar_key,
            template_filename="aset_qrar_template.json",
        )

        qr_result, ar_result = self._split_qr_ar_result(qrar_result)

        reading_annotated = self.annotator.annotate_sheet(reading_result)
        qrar_annotated = self.annotator.annotate_sheet(qrar_result)
        qrar_formatted = self.annotator.format_qrar_sections(qrar_annotated, qrar_result.template)

        cv2.imwrite(str(student_output_dir / "reading_marked.png"), reading_annotated)
        cv2.imwrite(str(student_output_dir / "qrar_marked.png"), qrar_formatted)
        cv2.imwrite(str(student_output_dir / "writing_page.png"), writing_page)

        analysis = self.analysis_service.generate_full_analysis(
            reading_result,
            qr_result,
            ar_result,
        )

        report_bytes = self.docx_generator.generate_report_bytes(
            student_data={
                "name": student.name,
                "writing_score": student.writing_score,
                "reading_score": reading_result.score,
                "reading_total": len(self.reading_answers),
                "qr_score": qr_result.score,
                "qr_total": len(self.qr_answers),
                "ar_score": ar_result.score,
                "ar_total": len(self.ar_answers),
            },
            flow_type="batch",
            analysis=analysis,
        )
        (student_output_dir / "report.docx").write_bytes(report_bytes)
        (student_output_dir / "analysis.json").write_text(
            json.dumps(asdict(analysis), indent=2),
            encoding="utf-8",
        )

        return StudentRunResult(
            name=student.name,
            status="Success",
            reading_score=float(reading_result.score),
            qr_score=float(qr_result.score),
            ar_score=float(ar_result.score),
            output_dir=student_output_dir,
        )

    def run_single(
        self,
        merged_doc_path: Path,
        student_name: str,
        writing_score: float,
        output_dir: Optional[Path] = None,
    ) -> SingleRunSummary:
        student = StudentInput(name=student_name, writing_score=float(writing_score))

        if output_dir is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.repo_root / "outputs" / f"desktop_single_{stamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        student_output_dir = output_dir / self._normalize_name(student.name)
        student_output_dir.mkdir(parents=True, exist_ok=True)

        result = self._process_student_document(student, merged_doc_path, student_output_dir)
        return SingleRunSummary(output_dir=output_dir, result=result)

    def run_batch(self, scans_path: Path, roster_path: Path, output_dir: Optional[Path] = None) -> BatchRunSummary:
        students = self.load_students_sheet(roster_path)
        docs = self._collect_merged_docs(scans_path)
        doc_map = self._map_students_to_docs(students, docs)

        if output_dir is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.repo_root / "outputs" / f"desktop_run_{stamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        results: List[StudentRunResult] = []

        for student in students:
            student_output_dir = output_dir / self._normalize_name(student.name)
            student_output_dir.mkdir(parents=True, exist_ok=True)

            try:
                results.append(
                    self._process_student_document(
                        student=student,
                        doc_path=doc_map[student.name],
                        student_output_dir=student_output_dir,
                    )
                )
            except Exception as exc:
                results.append(
                    StudentRunResult(
                        name=student.name,
                        status="Error",
                        notes=str(exc),
                        output_dir=student_output_dir,
                    )
                )

        summary_path = output_dir / "batch_summary.csv"
        with summary_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Student Name", "Status", "Reading Score", "QR Score", "AR Score", "Notes"])
            for item in results:
                writer.writerow(
                    [item.name, item.status, item.reading_score, item.qr_score, item.ar_score, item.notes]
                )

        return BatchRunSummary(output_dir=output_dir, results=results)

    def run(self, scans_path: Path, csv_path: Path, output_dir: Optional[Path] = None) -> BatchRunSummary:
        # Backward-compatible alias for legacy callers.
        return self.run_batch(scans_path=scans_path, roster_path=csv_path, output_dir=output_dir)
