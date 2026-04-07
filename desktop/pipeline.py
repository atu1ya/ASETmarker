from __future__ import annotations

import csv
import json
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from desktop.io import MergedDocumentSplitter
from desktop.services import AnalysisService, AnnotatorService, DocxReportGenerator, MarkingService
from desktop.services.marker import SubjectResult


SUPPORTED_SCAN_EXTENSIONS = {".pdf"}
SUPPORTED_ANSWER_KEY_EXTENSIONS = {".txt", ".csv"}
QUESTIONS_PER_SUBJECT = 35

EXPECTED_CSV_HEADERS = [
    "STUDENT NAME",
    "Reading Score (/35)",
    "Reading %",
    "Standardised Reading Score",
    "QR Score (/35)",
    "QR %",
    "Standardised QR Score",
    "AR score (/35)",
    "AR %",
    "Standardised AR Score",
    "Writing Score (/50)",
    "Writing %",
    "Standardised Writing Score",
    "Total Standard Score (/400)",
    "Total Score BEFORE standardising",
]

ANSWER_VALUE_PATTERN = re.compile(r"^[A-E]$", flags=re.IGNORECASE)
READING_LABEL_PATTERN = re.compile(r"^(?:R|RC|READING)\s*0*(\d+)$", flags=re.IGNORECASE)
QR_LABEL_PATTERN = re.compile(r"^(?:Q|QR|QUANTITATIVE(?:REASONING)?)\s*0*(\d+)$", flags=re.IGNORECASE)
AR_LABEL_PATTERN = re.compile(r"^(?:AR|ABSTRACT(?:REASONING)?)\s*0*(\d+)$", flags=re.IGNORECASE)


@dataclass
class StudentInput:
    name: str
    writing_percent: float


@dataclass
class AnswerKeyBundle:
    reading: List[str]
    qr: List[str]
    ar: List[str]


@dataclass
class StudentRunResult:
    name: str
    status: str
    reading_score: float = 0.0
    qr_score: float = 0.0
    ar_score: float = 0.0
    notes: str = ""


@dataclass
class BatchRunSummary:
    output_dir: Path
    results: List[StudentRunResult]


class DesktopBatchProcessor:
    def __init__(
        self,
        repo_root: Path,
        reading_answer_key_path: Path,
        qr_answer_key_path: Path,
        ar_answer_key_path: Path,
        concept_mapping_path: Path,
        year_level: str = "year4_5",
    ):
        self.repo_root = Path(repo_root)
        self.year_level = year_level
        self.config_dir = self.repo_root / "config"
        self.splitter = MergedDocumentSplitter()

        self.marking_service = MarkingService(self.config_dir)
        self.annotator = AnnotatorService()

        self.answer_keys = AnswerKeyBundle(
            reading=self._load_single_subject_answer_key(reading_answer_key_path, "reading"),
            qr=self._load_single_subject_answer_key(qr_answer_key_path, "qr"),
            ar=self._load_single_subject_answer_key(ar_answer_key_path, "ar"),
        )
        self.concept_mapping = self._load_concept_mapping(concept_mapping_path)

        self.analysis_service = AnalysisService(self.concept_mapping)
        self.docx_generator = DocxReportGenerator(
            year_level=year_level,
            concept_mapping=self.concept_mapping,
        )

    @staticmethod
    def _normalize_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @staticmethod
    def _safe_student_folder(value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9 _-]", "", value).strip()
        safe = re.sub(r"\s+", " ", safe)
        return safe if safe else "student"

    @staticmethod
    def _safe_student_file_stem(value: str) -> str:
        safe = DesktopBatchProcessor._safe_student_folder(value)
        safe = safe.replace(" ", "_")
        return safe if safe else "student"

    @staticmethod
    def _normalize_answer_token(token: str) -> Optional[str]:
        cleaned = re.sub(r"[^A-Za-z]", "", token or "").upper()
        if ANSWER_VALUE_PATTERN.match(cleaned):
            return cleaned
        return None

    @staticmethod
    def _parse_concept_questions(raw_questions: object) -> List[str]:
        if isinstance(raw_questions, list):
            return [str(item).strip() for item in raw_questions if str(item).strip()]
        if isinstance(raw_questions, str):
            return [item for item in re.split(r"[,\s]+", raw_questions) if item]
        return []

    def _extract_subject_mapping(
        self,
        raw_mapping: Dict[str, object],
        aliases: List[str],
    ) -> Dict[str, List[str]]:
        for alias in aliases:
            candidate = raw_mapping.get(alias)
            if not isinstance(candidate, dict):
                continue

            normalized: Dict[str, List[str]] = {}
            for concept_name, raw_questions in candidate.items():
                if not isinstance(concept_name, str):
                    continue
                questions = self._parse_concept_questions(raw_questions)
                if questions:
                    normalized[concept_name] = questions
            return normalized
        return {}

    def _load_concept_mapping(self, path: Path) -> Dict[str, Dict[str, List[str]]]:
        if not path.exists():
            raise FileNotFoundError(f"Concept mapping JSON file not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            raw_mapping = json.load(handle)

        if not isinstance(raw_mapping, dict):
            raise ValueError("Concept mapping JSON must contain a top-level object.")

        mapping = {
            "Reading": self._extract_subject_mapping(raw_mapping, ["Reading", "reading"]),
            "Quantitative Reasoning": self._extract_subject_mapping(
                raw_mapping,
                ["Quantitative Reasoning", "quantitative reasoning", "QR", "qr"],
            ),
            "Abstract Reasoning": self._extract_subject_mapping(
                raw_mapping,
                ["Abstract Reasoning", "abstract reasoning", "AR", "ar"],
            ),
        }

        if not mapping["Reading"]:
            raise ValueError("Concept mapping JSON must include a non-empty 'Reading' object.")
        if not mapping["Quantitative Reasoning"]:
            raise ValueError(
                "Concept mapping JSON must include a non-empty 'Quantitative Reasoning' object."
            )

        return mapping

    @staticmethod
    def _parse_label_token(token: str) -> Optional[Tuple[str, int]]:
        normalized = token.strip().upper()

        reading_match = READING_LABEL_PATTERN.match(normalized)
        if reading_match:
            return "reading", int(reading_match.group(1))

        qr_match = QR_LABEL_PATTERN.match(normalized)
        if qr_match:
            return "qr", int(qr_match.group(1))

        ar_match = AR_LABEL_PATTERN.match(normalized)
        if ar_match:
            return "ar", int(ar_match.group(1))

        if normalized.isdigit():
            value = int(normalized)
            if 1 <= value <= QUESTIONS_PER_SUBJECT:
                return "reading", value
            if QUESTIONS_PER_SUBJECT < value <= QUESTIONS_PER_SUBJECT * 2:
                return "qr", value - QUESTIONS_PER_SUBJECT
            if QUESTIONS_PER_SUBJECT * 2 < value <= QUESTIONS_PER_SUBJECT * 3:
                return "ar", value - (QUESTIONS_PER_SUBJECT * 2)

        return None

    @staticmethod
    def _is_answer_key_header_row(cells: List[str]) -> bool:
        if not cells:
            return False
        normalized = [re.sub(r"[^a-z]", "", cell.lower()) for cell in cells if cell]
        if not normalized:
            return False

        if len(normalized) == 1 and normalized[0] in {"answer", "answers", "key"}:
            return True

        joined = " ".join(normalized)
        return "question" in joined and "answer" in joined

    def _parse_labeled_cells(self, cells: List[str]) -> Optional[Tuple[str, int, str]]:
        for cell in cells:
            parsed = self._parse_labeled_answer(cell)
            if parsed is not None:
                return parsed

        parsed_joined = self._parse_labeled_answer(",".join(cells))
        if parsed_joined is not None:
            return parsed_joined

        for label_token in cells:
            parsed_label = self._parse_label_token(label_token)
            if not parsed_label:
                continue
            for answer_token in cells:
                if answer_token == label_token:
                    continue
                normalized_answer = self._normalize_answer_token(answer_token)
                if normalized_answer:
                    section, question_number = parsed_label
                    return section, question_number, normalized_answer

        return None

    def _parse_labeled_answer(self, line: str) -> Optional[Tuple[str, int, str]]:
        tokens = [token for token in re.split(r"[\s,:;=|]+", line) if token]
        if len(tokens) < 2:
            return None

        candidate_pairs: List[Tuple[str, str]] = [(tokens[0], tokens[1])]
        if len(tokens) >= 2:
            candidate_pairs.append((tokens[1], tokens[0]))

        for label_token, answer_token in candidate_pairs:
            parsed_label = self._parse_label_token(label_token)
            normalized_answer = self._normalize_answer_token(answer_token)
            if not parsed_label or not normalized_answer:
                continue

            section, question_number = parsed_label
            return section, question_number, normalized_answer

        return None

    @staticmethod
    def _extract_question_number_from_token(token: str) -> Optional[int]:
        match = re.search(r"(\d+)$", token.strip())
        if not match:
            return None
        return int(match.group(1))

    def _parse_subject_labeled_answer(self, line: str) -> Optional[Tuple[int, str]]:
        tokens = [token for token in re.split(r"[\s,:;=|]+", line) if token]
        if len(tokens) < 2:
            return None

        candidate_pairs: List[Tuple[str, str]] = []
        candidate_pairs.append((tokens[0], tokens[1]))
        candidate_pairs.append((tokens[1], tokens[0]))

        for label_token, answer_token in candidate_pairs:
            question_number = self._extract_question_number_from_token(label_token)
            answer = self._normalize_answer_token(answer_token)
            if question_number is None or answer is None:
                continue
            return question_number, answer

        for label_token in tokens:
            question_number = self._extract_question_number_from_token(label_token)
            if question_number is None:
                continue
            for answer_token in tokens:
                if answer_token == label_token:
                    continue
                answer = self._normalize_answer_token(answer_token)
                if answer is not None:
                    return question_number, answer

        return None

    def _parse_subject_labeled_cells(self, cells: List[str]) -> Optional[Tuple[int, str]]:
        for cell in cells:
            parsed = self._parse_subject_labeled_answer(cell)
            if parsed is not None:
                return parsed

        return self._parse_subject_labeled_answer(",".join(cells))

    def _load_single_subject_answer_key(self, path: Path, subject: str) -> List[str]:
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_ANSWER_KEY_EXTENSIONS:
            raise ValueError(
                f"{subject.upper()} answer key file must be .txt or .csv format."
            )
        if not path.exists():
            raise FileNotFoundError(f"{subject.upper()} answer key file not found: {path}")

        indexed_answers: Dict[int, str] = {}
        sequential_answers: List[str] = []

        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                for row_number, row in enumerate(reader, start=1):
                    cells = [str(cell).strip() for cell in row if str(cell).strip()]
                    if not cells:
                        continue

                    if row_number == 1 and self._is_answer_key_header_row(cells):
                        continue

                    labeled = self._parse_subject_labeled_cells(cells)
                    if labeled is not None:
                        question_number, answer = labeled
                        if not 1 <= question_number <= QUESTIONS_PER_SUBJECT:
                            raise ValueError(
                                f"{subject.upper()} answer key CSV row {row_number} has out-of-range question number: {row}"
                            )
                        existing = indexed_answers.get(question_number)
                        if existing is not None and existing != answer:
                            raise ValueError(
                                f"Conflicting answers for {subject.upper()} Q{question_number}: {existing} vs {answer}"
                            )
                        indexed_answers[question_number] = answer
                        continue

                    if len(cells) == 1:
                        answer = self._normalize_answer_token(cells[0])
                        if answer is not None:
                            sequential_answers.append(answer)
                            continue

                    raise ValueError(
                        f"Could not parse {subject.upper()} answer key CSV row {row_number}: {row}"
                    )
        else:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    line = raw_line.split("#", 1)[0].strip()
                    if not line:
                        continue

                    labeled = self._parse_subject_labeled_answer(line)
                    if labeled is not None:
                        question_number, answer = labeled
                        if not 1 <= question_number <= QUESTIONS_PER_SUBJECT:
                            raise ValueError(
                                f"{subject.upper()} answer key line {line_number} has out-of-range question number: {line}"
                            )
                        existing = indexed_answers.get(question_number)
                        if existing is not None and existing != answer:
                            raise ValueError(
                                f"Conflicting answers for {subject.upper()} Q{question_number}: {existing} vs {answer}"
                            )
                        indexed_answers[question_number] = answer
                        continue

                    answer = self._normalize_answer_token(line)
                    if answer is not None:
                        sequential_answers.append(answer)
                        continue

                    raise ValueError(
                        f"Could not parse {subject.upper()} answer key line {line_number}: '{raw_line.rstrip()}'"
                    )

        if indexed_answers and sequential_answers:
            raise ValueError(
                f"{subject.upper()} answer key cannot mix labeled rows and unlabeled rows."
            )

        if indexed_answers:
            missing = [
                idx
                for idx in range(1, QUESTIONS_PER_SUBJECT + 1)
                if idx not in indexed_answers
            ]
            if missing:
                raise ValueError(
                    f"{subject.upper()} answer key is missing answers for questions: {missing[:6]}"
                )
            return [indexed_answers[idx] for idx in range(1, QUESTIONS_PER_SUBJECT + 1)]

        if len(sequential_answers) != QUESTIONS_PER_SUBJECT:
            raise ValueError(
                f"{subject.upper()} answer key must contain exactly {QUESTIONS_PER_SUBJECT} answers in unlabeled format. "
                f"Found {len(sequential_answers)}."
            )

        return sequential_answers

    def _load_answer_key(self, path: Path) -> AnswerKeyBundle:
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_ANSWER_KEY_EXTENSIONS:
            raise ValueError(
                "Answer key file must be .txt or .csv format."
            )
        if not path.exists():
            raise FileNotFoundError(f"Answer key file not found: {path}")

        section_answers: Dict[str, Dict[int, str]] = {
            "reading": {},
            "qr": {},
            "ar": {},
        }
        unlabeled_answers: List[str] = []

        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                for row_number, row in enumerate(reader, start=1):
                    cells = [str(cell).strip() for cell in row if str(cell).strip()]
                    if not cells:
                        continue

                    if row_number == 1 and self._is_answer_key_header_row(cells):
                        continue

                    labeled = self._parse_labeled_cells(cells)
                    if labeled is not None:
                        section, question_number, answer = labeled
                        if not 1 <= question_number <= QUESTIONS_PER_SUBJECT:
                            raise ValueError(
                                f"Answer key CSV row {row_number} has out-of-range question number: {row}"
                            )
                        existing = section_answers[section].get(question_number)
                        if existing is not None and existing != answer:
                            raise ValueError(
                                f"Conflicting answers for {section.upper()}{question_number}: {existing} vs {answer}"
                            )
                        section_answers[section][question_number] = answer
                        continue

                    if len(cells) == 1:
                        normalized = self._normalize_answer_token(cells[0])
                        if normalized:
                            unlabeled_answers.append(normalized)
                            continue

                    raise ValueError(
                        f"Could not parse answer key CSV row {row_number}: {row}"
                    )
        else:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    line = raw_line.split("#", 1)[0].strip()
                    if not line:
                        continue

                    labeled = self._parse_labeled_answer(line)
                    if labeled is not None:
                        section, question_number, answer = labeled
                        if not 1 <= question_number <= QUESTIONS_PER_SUBJECT:
                            raise ValueError(
                                f"Answer key line {line_number} has out-of-range question number: {line}"
                            )

                        existing = section_answers[section].get(question_number)
                        if existing is not None and existing != answer:
                            raise ValueError(
                                f"Conflicting answers for {section.upper()}{question_number}: {existing} vs {answer}"
                            )
                        section_answers[section][question_number] = answer
                        continue

                    normalized = self._normalize_answer_token(line)
                    if normalized:
                        unlabeled_answers.append(normalized)
                        continue

                    raise ValueError(
                        f"Could not parse answer key line {line_number}: '{raw_line.rstrip()}'"
                    )

        has_labeled_answers = any(section_answers[section] for section in section_answers)
        if has_labeled_answers:
            if unlabeled_answers:
                raise ValueError(
                    "Answer key TXT cannot mix labeled rows (e.g., RC1 A) and unlabeled rows (e.g., A)."
                )

            resolved_sections: Dict[str, List[str]] = {}
            for section in ["reading", "qr", "ar"]:
                missing = [
                    idx
                    for idx in range(1, QUESTIONS_PER_SUBJECT + 1)
                    if idx not in section_answers[section]
                ]
                if missing:
                    raise ValueError(
                        f"Answer key TXT is missing {section.upper()} answers for questions: {missing[:6]}"
                    )
                resolved_sections[section] = [
                    section_answers[section][idx]
                    for idx in range(1, QUESTIONS_PER_SUBJECT + 1)
                ]

            return AnswerKeyBundle(
                reading=resolved_sections["reading"],
                qr=resolved_sections["qr"],
                ar=resolved_sections["ar"],
            )

        total_needed = QUESTIONS_PER_SUBJECT * 3
        if len(unlabeled_answers) != total_needed:
            raise ValueError(
                f"Answer key TXT must contain exactly {total_needed} answers (35 Reading + 35 QR + 35 AR) "
                f"when using unlabeled format. Found {len(unlabeled_answers)}."
            )

        return AnswerKeyBundle(
            reading=unlabeled_answers[0:QUESTIONS_PER_SUBJECT],
            qr=unlabeled_answers[QUESTIONS_PER_SUBJECT : QUESTIONS_PER_SUBJECT * 2],
            ar=unlabeled_answers[QUESTIONS_PER_SUBJECT * 2 : QUESTIONS_PER_SUBJECT * 3],
        )

    def load_students_csv(self, csv_path: Path) -> List[StudentInput]:
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("Student CSV must include headers.")

            headers = [header.strip() for header in reader.fieldnames if header is not None]
            missing_headers = [header for header in EXPECTED_CSV_HEADERS if header not in headers]
            if missing_headers:
                raise ValueError(
                    "Student CSV is missing expected headers: " + ", ".join(missing_headers)
                )

            students: List[StudentInput] = []
            for row in reader:
                raw_name = str(row.get("STUDENT NAME", "")).strip()
                if not raw_name:
                    continue
                raw_writing = str(row.get("Writing %", "")).strip().replace("%", "")
                if not raw_writing:
                    raise ValueError(f"Missing Writing % for student: {raw_name}")

                try:
                    writing_percent = float(raw_writing)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid Writing % '{raw_writing}' for student: {raw_name}"
                    ) from exc

                students.append(StudentInput(name=raw_name, writing_percent=writing_percent))

            if not students:
                raise ValueError("Student CSV did not contain any student rows.")
            return students

    def _collect_merged_docs(self, scans_path: Path) -> List[Path]:
        if scans_path.is_file():
            if scans_path.suffix.lower() not in SUPPORTED_SCAN_EXTENSIONS:
                raise ValueError(f"Unsupported scan file type: {scans_path}")
            return [scans_path]

        if not scans_path.is_dir():
            raise FileNotFoundError(f"Scan path does not exist: {scans_path}")

        files = [p for p in scans_path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
        if not files:
            raise ValueError(f"No merged PDF files found in: {scans_path}")
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

    @staticmethod
    def _encode_png_bytes(img: np.ndarray) -> bytes:
        ok, encoded = cv2.imencode(".png", img)
        if not ok:
            raise ValueError("Could not encode page image for marking.")
        return encoded.tobytes()

    @staticmethod
    def _write_image_as_pdf(image: np.ndarray, output_path: Path) -> None:
        if image.ndim == 3 and image.shape[2] == 3:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
        else:
            pil_image = Image.fromarray(image)
        pil_image.save(output_path, format="PDF", resolution=220.0)

    @staticmethod
    def _create_missing_writing_pdf(student_name: str, source_doc: Path, page_count: int) -> bytes:
        from io import BytesIO

        canvas = Image.new("RGB", (1654, 2339), color="white")
        draw = ImageDraw.Draw(canvas)

        lines = [
            "ASET Marker - Writing Sheet Placeholder",
            "",
            f"Student: {student_name}",
            f"Source file: {source_doc.name}",
            f"Detected pages: {page_count}",
            "",
            "No writing scan page was supplied in the merged document.",
            "Reading and QR/AR marking completed successfully.",
        ]

        y = 120
        for line in lines:
            draw.text((120, y), line, fill=(32, 32, 32))
            y += 58

        buffer = BytesIO()
        canvas.save(buffer, format="PDF", resolution=220.0)
        return buffer.getvalue()

    @staticmethod
    def _append_debug_log(log_path: Path, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")

    def _split_qr_ar_result(self, qrar_result: SubjectResult) -> Tuple[SubjectResult, SubjectResult]:
        qr_len = len(self.answer_keys.qr)
        ar_len = len(self.answer_keys.ar)

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

    def run(self, scans_path: Path, csv_path: Path, output_dir: Optional[Path] = None) -> BatchRunSummary:
        students = self.load_students_csv(csv_path)
        docs = self._collect_merged_docs(scans_path)
        doc_map = self._map_students_to_docs(students, docs)

        if output_dir is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = self.repo_root / "outputs" / f"desktop_run_{stamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        debug_log_path = output_dir / "debug_run.log"
        self._append_debug_log(debug_log_path, "Desktop batch run started.")
        self._append_debug_log(debug_log_path, f"Scans path: {scans_path}")
        self._append_debug_log(debug_log_path, f"CSV path: {csv_path}")
        self._append_debug_log(debug_log_path, f"Students in CSV: {len(students)}")
        self._append_debug_log(debug_log_path, f"Merged documents discovered: {len(docs)}")

        results: List[StudentRunResult] = []

        for student in students:
            student_output_dir = output_dir / self._safe_student_folder(student.name)
            student_output_dir.mkdir(parents=True, exist_ok=True)
            source_doc = doc_map[student.name]
            student_file_stem = self._safe_student_file_stem(student.name)
            self._append_debug_log(
                debug_log_path,
                f"Student '{student.name}' start. Source document: {source_doc}",
            )

            try:
                split_pages = self.splitter.split_document(source_doc)
                reading_page = split_pages.reading_page_gray
                qrar_page = split_pages.qrar_page_gray
                writing_pdf = split_pages.writing_page_pdf
                self._append_debug_log(
                    debug_log_path,
                    f"Student '{student.name}' page_count={split_pages.page_count}",
                )
                for warning in split_pages.warnings:
                    self._append_debug_log(
                        debug_log_path,
                        f"Student '{student.name}' warning: {warning}",
                    )

                if writing_pdf is None:
                    writing_pdf = self._create_missing_writing_pdf(
                        student_name=student.name,
                        source_doc=source_doc,
                        page_count=split_pages.page_count,
                    )
                    self._append_debug_log(
                        debug_log_path,
                        f"Student '{student.name}' missing writing page: placeholder writing_sheet.pdf generated.",
                    )

                reading_bytes = self._encode_png_bytes(reading_page)
                qrar_bytes = self._encode_png_bytes(qrar_page)

                reading_key = {f"RC{i+1}": ans for i, ans in enumerate(self.answer_keys.reading)}
                qrar_key: Dict[str, str] = {}
                for i, ans in enumerate(self.answer_keys.qr):
                    qrar_key[f"QR{i+1}"] = ans
                for i, ans in enumerate(self.answer_keys.ar):
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
                qrar_annotated = self.annotator.annotate_sheet(
                    qrar_result,
                    include_score_overlay=False,
                )
                qrar_formatted = self.annotator.format_qrar_sections(
                    qrar_annotated,
                    qrar_result.template,
                    qr_score=qr_result.score,
                    qr_total=len(self.answer_keys.qr),
                    ar_score=ar_result.score,
                    ar_total=len(self.answer_keys.ar),
                )

                self._write_image_as_pdf(
                    reading_annotated,
                    student_output_dir / f"{student_file_stem}_reading.pdf",
                )
                self._write_image_as_pdf(
                    qrar_formatted,
                    student_output_dir / f"{student_file_stem}_qrar.pdf",
                )
                (student_output_dir / f"{student_file_stem}_writing.pdf").write_bytes(writing_pdf)

                analysis = self.analysis_service.generate_full_analysis(
                    reading_result,
                    qr_result,
                    ar_result,
                )

                student_payload = {
                    "name": student.name,
                    "writing_score": student.writing_percent,
                    "reading_score": reading_result.score,
                    "reading_total": len(self.answer_keys.reading),
                    "qr_score": qr_result.score,
                    "qr_total": len(self.answer_keys.qr),
                    "ar_score": ar_result.score,
                    "ar_total": len(self.answer_keys.ar),
                }

                report_bytes = self.docx_generator.generate_report_bytes(
                    student_data=student_payload,
                    flow_type="batch",
                    analysis=analysis,
                )
                (student_output_dir / f"{student_file_stem}_report.docx").write_bytes(report_bytes)

                graph_bytes = self.docx_generator.generate_chart_bytes(
                    student_data=student_payload,
                    flow_type="batch",
                    analysis=analysis,
                )
                (student_output_dir / "performance_graph.png").write_bytes(graph_bytes)
                self._append_debug_log(
                    debug_log_path,
                    (
                        f"Student '{student.name}' success. "
                        f"Scores -> Reading={reading_result.score}, QR={qr_result.score}, AR={ar_result.score}"
                    ),
                )

                results.append(
                    StudentRunResult(
                        name=student.name,
                        status="Success",
                        reading_score=float(reading_result.score),
                        qr_score=float(qr_result.score),
                        ar_score=float(ar_result.score),
                    )
                )
            except Exception as exc:
                trace = traceback.format_exc()
                (student_output_dir / "debug_error.txt").write_text(trace, encoding="utf-8")
                self._append_debug_log(
                    debug_log_path,
                    f"Student '{student.name}' error: {exc}\n{trace}",
                )
                results.append(StudentRunResult(name=student.name, status="Error", notes=str(exc)))

        summary_path = output_dir / "batch_summary.csv"
        with summary_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Student Name", "Status", "Reading Score", "QR Score", "AR Score", "Notes"])
            for item in results:
                writer.writerow(
                    [item.name, item.status, item.reading_score, item.qr_score, item.ar_score, item.notes]
                )

        success_count = sum(1 for item in results if item.status == "Success")
        failure_count = len(results) - success_count
        self._append_debug_log(
            debug_log_path,
            f"Run completed. Success={success_count}, Failed={failure_count}",
        )

        return BatchRunSummary(output_dir=output_dir, results=results)
