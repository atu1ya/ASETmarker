from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from docx.shared import Inches
from docxtpl import DocxTemplate, InlineImage

from desktop.services.docx_report import (
    DEFAULT_QR_CONCEPTS,
    DEFAULT_READING_CONCEPTS,
    DocxReportGenerator,
    FlowType,
)


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


@dataclass
class PrecalculatedStudentRow:
    student_name: str
    reading_percent: float
    standardised_reading_score: float
    qr_percent: float
    standardised_qr_score: float
    ar_percent: float
    standardised_ar_score: float
    writing_percent: float
    standardised_writing_score: float
    total_standard_score: float
    total_score_before_standardising: float


@dataclass
class CSVReportBatchSummary:
    output_dir: Path
    total_students: int
    generated_reports: int
    failed_reports: List[str]
    generated_files: List[Path]


def _parse_float(raw_value: object, column_name: str, row_number: int) -> float:
    value = "" if raw_value is None else str(raw_value).strip()
    if not value:
        raise ValueError(f"Row {row_number}: '{column_name}' is empty.")

    normalized = value.replace(",", "").replace("%", "")
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Row {row_number}: '{column_name}' has invalid numeric value '{value}'."
        ) from exc


EXPECTED_HEADER_ALIASES = {
    "STUDENT NAME": [
        "student name",
        "student_name",
        "name",
    ],
    "Reading Score (/35)": [
        "reading score (/35)",
        "reading score",
        "reading raw score",
    ],
    "Reading %": [
        "reading %",
        "reading percent",
    ],
    "Standardised Reading Score": [
        "standardised reading score",
        "standardized reading score",
    ],
    "QR Score (/35)": [
        "qr score (/35)",
        "qr score",
        "quantitative reasoning score (/35)",
        "quantitative reasoning score",
    ],
    "QR %": [
        "qr %",
        "qr percent",
        "quantitative reasoning %",
        "quantitative reasoning percent",
    ],
    "Standardised QR Score": [
        "standardised qr score",
        "standardized qr score",
        "standardised quantitative reasoning score",
        "standardized quantitative reasoning score",
    ],
    "AR score (/35)": [
        "ar score (/35)",
        "ar score",
        "abstract reasoning score (/35)",
        "abstract reasoning score",
    ],
    "AR %": [
        "ar %",
        "ar percent",
        "abstract reasoning %",
        "abstract reasoning percent",
    ],
    "Standardised AR Score": [
        "standardised ar score",
        "standardized ar score",
        "standardised abstract reasoning score",
        "standardized abstract reasoning score",
    ],
    "Writing Score (/50)": [
        "writing score (/50)",
        "writing score",
        "writing raw score",
    ],
    "Writing %": [
        "writing %",
        "writing percent",
    ],
    "Standardised Writing Score": [
        "standardised writing score",
        "standardized writing score",
    ],
    "Total Standard Score (/400)": [
        "total standard score (/400)",
        "total standard score",
    ],
    "Total Score BEFORE standardising": [
        "total score before standardising",
        "total score before standardizing",
        "total score before standardisation",
    ],
}


EXPECTED_HEADER_REQUIRED_TOKENS = {
    "STUDENT NAME": {"student", "name"},
    "Reading Score (/35)": {"reading", "score", "35"},
    "Reading %": {"reading", "percent"},
    "Standardised Reading Score": {"standardised", "reading", "score"},
    "QR Score (/35)": {"qr", "score", "35"},
    "QR %": {"qr", "percent"},
    "Standardised QR Score": {"standardised", "qr", "score"},
    "AR score (/35)": {"ar", "score", "35"},
    "AR %": {"ar", "percent"},
    "Standardised AR Score": {"standardised", "ar", "score"},
    "Writing Score (/50)": {"writing", "score", "50"},
    "Writing %": {"writing", "percent"},
    "Standardised Writing Score": {"standardised", "writing", "score"},
    "Total Standard Score (/400)": {"total", "standard", "score", "400"},
    "Total Score BEFORE standardising": {
        "total",
        "score",
        "before",
        "standardising",
    },
}


def _header_tokens(value: str) -> List[str]:
    normalized = value.strip().lower()
    normalized = normalized.replace("%", " percent ")
    normalized = normalized.replace("standardized", "standardised")
    normalized = normalized.replace("standardizing", "standardising")
    normalized = normalized.replace("quantitative reasoning", "qr")
    normalized = normalized.replace("abstract reasoning", "ar")
    return re.findall(r"[a-z0-9]+", normalized)


def _canonical_header(value: str) -> str:
    return "".join(_header_tokens(value))


def _cell_is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return all(_cell_is_empty(item) for item in value)
    return str(value).strip() == ""


def _row_is_empty(row: Mapping[Any, Any]) -> bool:
    return all(_cell_is_empty(value) for value in row.values())


def _validate_csv_headers(fieldnames: Optional[Sequence[str]]) -> Dict[str, str]:
    if not fieldnames:
        raise ValueError("CSV is missing header row.")

    actual_headers = [name.strip() for name in fieldnames if name and name.strip()]
    if not actual_headers:
        raise ValueError("CSV is missing header row.")

    actual_token_map = {header: set(_header_tokens(header)) for header in actual_headers}
    actual_canonical_map: Dict[str, List[str]] = {}
    for header in actual_headers:
        actual_canonical_map.setdefault(_canonical_header(header), []).append(header)

    resolved: Dict[str, str] = {}
    used_actual_headers: set[str] = set()
    unresolved: List[str] = []
    ambiguous: List[str] = []

    for expected_header in EXPECTED_CSV_HEADERS:
        alias_values = EXPECTED_HEADER_ALIASES.get(expected_header, [expected_header])
        canonical_aliases = {_canonical_header(alias) for alias in alias_values + [expected_header]}

        direct_matches: List[str] = []
        for canonical_alias in canonical_aliases:
            direct_matches.extend(actual_canonical_map.get(canonical_alias, []))
        direct_matches = list(dict.fromkeys(direct_matches))

        available_direct_matches = [
            header for header in direct_matches if header not in used_actual_headers
        ]

        if len(available_direct_matches) == 1:
            resolved[expected_header] = available_direct_matches[0]
            used_actual_headers.add(available_direct_matches[0])
            continue

        if len(available_direct_matches) > 1:
            ambiguous.append(
                f"{expected_header} -> {', '.join(available_direct_matches)}"
            )
            continue

        expected_tokens = EXPECTED_HEADER_REQUIRED_TOKENS[expected_header]
        token_matches = [
            header
            for header, tokens in actual_token_map.items()
            if header not in used_actual_headers and expected_tokens.issubset(tokens)
        ]

        if len(token_matches) == 1:
            resolved[expected_header] = token_matches[0]
            used_actual_headers.add(token_matches[0])
            continue

        if len(token_matches) > 1:
            ambiguous.append(f"{expected_header} -> {', '.join(token_matches)}")
            continue

        unresolved.append(expected_header)

    if unresolved or ambiguous:
        details: List[str] = []
        if unresolved:
            details.append(f"Missing columns: {', '.join(unresolved)}")
        if ambiguous:
            details.append(f"Ambiguous columns: {'; '.join(ambiguous)}")

        raise ValueError(
            "CSV headers do not match the required format. Matching is case-insensitive and "
            "tolerates punctuation/spacing variations. "
            + " ".join(details)
            + f" Required headers: {', '.join(EXPECTED_CSV_HEADERS)}"
        )

    return resolved


def parse_precalculated_csv(
    csv_path: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[PrecalculatedStudentRow]:
    rows: List[PrecalculatedStudentRow] = []
    skipped_blank_rows = 0

    try:
        with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if progress_callback:
                progress_callback("Validating CSV headers...")
            header_map = _validate_csv_headers(reader.fieldnames)
            if progress_callback:
                progress_callback("Headers validated. Reading student rows...")

            for row_number, row in enumerate(reader, start=2):
                if _row_is_empty(row):
                    skipped_blank_rows += 1
                    continue

                student_name = str(row.get(header_map["STUDENT NAME"], "")).strip()
                if not student_name:
                    raise ValueError(f"Row {row_number}: 'STUDENT NAME' is empty.")

                rows.append(
                    PrecalculatedStudentRow(
                        student_name=student_name,
                        reading_percent=_parse_float(
                            row.get(header_map["Reading %"]),
                            "Reading %",
                            row_number,
                        ),
                        standardised_reading_score=_parse_float(
                            row.get(header_map["Standardised Reading Score"]),
                            "Standardised Reading Score",
                            row_number,
                        ),
                        qr_percent=_parse_float(
                            row.get(header_map["QR %"]),
                            "QR %",
                            row_number,
                        ),
                        standardised_qr_score=_parse_float(
                            row.get(header_map["Standardised QR Score"]),
                            "Standardised QR Score",
                            row_number,
                        ),
                        ar_percent=_parse_float(
                            row.get(header_map["AR %"]),
                            "AR %",
                            row_number,
                        ),
                        standardised_ar_score=_parse_float(
                            row.get(header_map["Standardised AR Score"]),
                            "Standardised AR Score",
                            row_number,
                        ),
                        writing_percent=_parse_float(
                            row.get(header_map["Writing %"]),
                            "Writing %",
                            row_number,
                        ),
                        standardised_writing_score=_parse_float(
                            row.get(header_map["Standardised Writing Score"]),
                            "Standardised Writing Score",
                            row_number,
                        ),
                        total_standard_score=_parse_float(
                            row.get(header_map["Total Standard Score (/400)"]),
                            "Total Standard Score (/400)",
                            row_number,
                        ),
                        total_score_before_standardising=_parse_float(
                            row.get(header_map["Total Score BEFORE standardising"]),
                            "Total Score BEFORE standardising",
                            row_number,
                        ),
                    )
                )
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot open CSV file '{csv_path}'. It may be open in another application."
        ) from exc
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV file: {exc}") from exc

    if not rows:
        raise ValueError("CSV does not contain any student rows.")

    if progress_callback and skipped_blank_rows:
        progress_callback(
            f"Skipped {skipped_blank_rows} blank row(s) at the end of the CSV."
        )

    return rows


class CSVReportGenerator:
    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
        self.docx_generator = DocxReportGenerator()

    @staticmethod
    def _safe_name_token(student_name: str) -> str:
        """Sanitize a student name for safe use as a filesystem path component.

        Strips characters disallowed on Windows/POSIX (``<>:"/\\|?*`` and control
        chars) and trailing dots/spaces (a Windows restriction). Falls back to
        ``"Student"`` if the name reduces to nothing.
        """
        safe = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", student_name)
        safe = re.sub(r"\s+", " ", safe).strip()
        safe = safe.rstrip(". ")
        return safe or "Student"

    @staticmethod
    def _safe_output_filename(student_name: str) -> str:
        return f"{CSVReportGenerator._safe_name_token(student_name)}_ASET_Report.docx"

    @staticmethod
    def _safe_graph_filename(student_name: str) -> str:
        return f"{CSVReportGenerator._safe_name_token(student_name)}_Scores_Graph.png"

    def _build_empty_concept_rows(self, concept_names: List[str], subject_name: str) -> List[Dict[str, str]]:
        concepts = self.docx_generator._build_concept_mastery_list(
            concept_names=concept_names,
            subject_name=subject_name,
            area_results=None,
            flow_type=FlowType.MOCK,
        )
        return [
            {
                "name": concept.name,
                "questions": concept.questions,
                "question_numbers": concept.questions,
                "done_well": concept.done_well,
                "improve": concept.improve,
                "done_well_tick": concept.done_well,
                "room_improve_tick": concept.improve,
            }
            for concept in concepts
        ]

    def _build_template_context(self, student: PrecalculatedStudentRow) -> Dict[str, Any]:
        reading_concepts = self._build_empty_concept_rows(DEFAULT_READING_CONCEPTS, "Reading")
        qr_concepts = self._build_empty_concept_rows(DEFAULT_QR_CONCEPTS, "Quantitative Reasoning")

        reading_percentage = round(student.reading_percent, 2)
        qr_percentage = round(student.qr_percent, 2)
        ar_percentage = round(student.ar_percent, 2)
        writing_percentage = round(student.writing_percent, 2)

        reading_standard = round(student.standardised_reading_score, 2)
        qr_standard = round(student.standardised_qr_score, 2)
        ar_standard = round(student.standardised_ar_score, 2)
        writing_standard = round(student.standardised_writing_score, 2)

        total_standard = round(student.total_standard_score, 2)

        return {
            "student_name": student.student_name.title(),
            "total_score": total_standard,
            "writing_score": writing_percentage,
            "writing_percentage": writing_percentage,
            "standardised_writing_score": writing_standard,
            "rc": {
                "score": reading_standard,
                "total": 100.0,
                "percentage": reading_percentage,
                "concepts": reading_concepts,
            },
            "qr": {
                "score": qr_standard,
                "total": 100.0,
                "percentage": qr_percentage,
                "concepts": qr_concepts,
            },
            "ar": {
                "score": ar_standard,
                "total": 100.0,
                "percentage": ar_percentage,
            },
            "reading": {
                "score": reading_standard,
                "total": 100.0,
                "percentage": reading_percentage,
                "concepts": reading_concepts,
            },
            "reading_score": reading_percentage,
            "qr_score": qr_percentage,
            "ar_score": ar_percentage,
            "reading_concepts": reading_concepts,
            "qr_concepts": qr_concepts,
            "standardised_reading_score": reading_standard,
            "standardised_qr_score": qr_standard,
            "standardised_ar_score": ar_standard,
            "total_score_before_standardising": round(student.total_score_before_standardising, 2),
        }

    def _generate_report_bytes(self, context: Dict[str, Any]) -> tuple[bytes, bytes]:
        doc = DocxTemplate(self.docx_generator.template_path)

        scores = {
            "Reading": float(context["rc"]["percentage"]),
            "Writing": float(context["writing_percentage"]),
            "QR": float(context["qr"]["percentage"]),
            "AR": float(context["ar"]["percentage"]),
            "Total": float(context["total_score"]),
        }

        chart_buffer = self.docx_generator._create_bar_chart(
            str(context["student_name"]),
            scores,
        )
        chart_bytes = chart_buffer.getvalue()
        chart_buffer.seek(0)
        context["graph_image"] = InlineImage(doc, chart_buffer, width=Inches(5))

        doc.render(context)

        for table in doc.tables:
            table.autofit = False

        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        return output.getvalue(), chart_bytes

    def generate_reports(
        self,
        csv_path: Path,
        output_dir: Path,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> CSVReportBatchSummary:
        if progress_callback:
            progress_callback("Opening CSV file...")

        students = parse_precalculated_csv(
            csv_path,
            progress_callback=progress_callback,
        )

        output_dir = Path(output_dir)
        if progress_callback:
            progress_callback("Preparing output directory...")
        output_dir.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(f"Parsed {len(students)} students from CSV.")

        generated_files: List[Path] = []
        failed_reports: List[str] = []

        for index, student in enumerate(students, start=1):
            if progress_callback:
                progress_callback(
                    f"[{index}/{len(students)}] Generating report for {student.student_name}..."
                )

            try:
                context = self._build_template_context(student)
                report_bytes, chart_bytes = self._generate_report_bytes(context)

                student_dir = output_dir / self._safe_name_token(student.student_name)
                student_dir.mkdir(parents=True, exist_ok=True)

                report_path = student_dir / self._safe_output_filename(student.student_name)
                report_path.write_bytes(report_bytes)
                generated_files.append(report_path)

                graph_path = student_dir / self._safe_graph_filename(student.student_name)
                graph_path.write_bytes(chart_bytes)
                generated_files.append(graph_path)

                if progress_callback:
                    progress_callback(
                        f"Saved {report_path.name} and {graph_path.name} to {student_dir.name}/"
                    )
            except PermissionError as exc:
                message = (
                    f"{student.student_name}: Could not write report file because it is in use. "
                    f"{exc}"
                )
                failed_reports.append(message)
                if progress_callback:
                    progress_callback(f"Error: {message}")
            except Exception as exc:
                message = f"{student.student_name}: {exc}"
                failed_reports.append(message)
                if progress_callback:
                    progress_callback(f"Error: {message}")

        if progress_callback:
            progress_callback(
                (
                    "Report generation finished. "
                    f"Success: {len(generated_files)}, Failed: {len(failed_reports)}"
                )
            )

        return CSVReportBatchSummary(
            output_dir=output_dir,
            total_students=len(students),
            generated_reports=len(generated_files),
            failed_reports=failed_reports,
            generated_files=generated_files,
        )