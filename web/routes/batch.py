"""Batch processing routes."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from web.app import templates
from web.config import Settings
from web.dependencies import get_settings, require_configuration
from web.services import AnalysisService, AnnotatorService, MarkingService, ReportService
from web.session_store import MarkingConfiguration

router = APIRouter()


def _pop_flash_messages(request: Request) -> list[dict[str, str]]:
    messages = request.session.get("flash_messages", [])
    request.session["flash_messages"] = []
    return messages


def _sanitize_name(name: str) -> str:
    sanitized = "_".join(part for part in name.strip().split() if part)
    return sanitized or "student"


def _validate_extension(upload: UploadFile, allowed: set[str]) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type for {upload.filename}",
        )


def _validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    students = manifest.get("students")
    if not isinstance(students, list) or not students:
        return ["Manifest must include a non-empty 'students' list."]

    for idx, student in enumerate(students, start=1):
        if not isinstance(student, dict):
            errors.append(f"Student entry #{idx} must be an object.")
            continue
        name = student.get("name")
        writing_score = student.get("writing_score")
        reading_file = student.get("reading_file")
        qrar_file = student.get("qrar_file")

        if not isinstance(name, str) or not name.strip():
            errors.append(f"Student #{idx} is missing a valid name.")
        if not isinstance(writing_score, int) or not (0 <= writing_score <= 100):
            errors.append(f"Student '{name or idx}' has an invalid writing score (0-100).")
        if not isinstance(reading_file, str) or not reading_file:
            errors.append(f"Student '{name or idx}' must specify 'reading_file'.")
        if not isinstance(qrar_file, str) or not qrar_file:
            errors.append(f"Student '{name or idx}' must specify 'qrar_file'.")
    return errors


@router.get("")
async def batch_page(request: Request, config: MarkingConfiguration = Depends(require_configuration)):
    """Render the batch processing page."""
    summary = {
        "reading_questions": len(config.reading_answers),
        "qrar_questions": len(config.qrar_answers),
        "subjects": [
            subject for subject in config.concept_mapping.keys() if not subject.startswith("_")
        ],
    }
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "config_summary": summary,
            "messages": _pop_flash_messages(request),
        },
    )


@router.post("/process")
async def process_batch(
    manifest: UploadFile = File(...),
    sheets_zip: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    config: MarkingConfiguration = Depends(require_configuration),
):
    """Process batch uploads and return a ZIP archive with per-student results."""
    _validate_extension(manifest, {".json"})
    _validate_extension(sheets_zip, {".zip"})

    manifest_data = (await manifest.read()).decode("utf-8", errors="ignore")
    try:
        manifest_json = json.loads(manifest_data)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manifest file must contain valid JSON.",
        ) from exc

    manifest_errors = _validate_manifest(manifest_json)
    if manifest_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(manifest_errors),
        )

    sheets_bytes = await sheets_zip.read()
    size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(sheets_bytes) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded ZIP exceeds the allowed size for batch processing.",
        )

    marking_service = MarkingService(settings.CONFIG_DIR)
    analysis_service = AnalysisService(config.concept_mapping)
    report_service = ReportService(settings.ASSETS_DIR)
    annotator_service = AnnotatorService()

    output_buffer = io.BytesIO()
    try:
        sheets_io = io.BytesIO(sheets_bytes)
        with ZipFile(sheets_io) as sheets_archive_ctx, ZipFile(output_buffer, "w") as results_zip:
        for student in manifest_json["students"]:
            student_name = student["name"]
            writing_score = student["writing_score"]
            reading_file = student["reading_file"]
            qrar_file = student["qrar_file"]

            try:
                reading_bytes = sheets_archive_ctx.read(reading_file)
                qrar_bytes = sheets_archive_ctx.read(qrar_file)
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing file '{exc.args[0]}' in sheets ZIP.",
                ) from exc

            reading_result = marking_service.mark_reading_sheet(reading_bytes, config.reading_answers)
            qrar_result = marking_service.mark_qrar_sheet(qrar_bytes, config.qrar_answers)

            reading_score = reading_result["results"]
            qr_score = qrar_result["qr"]
            ar_score = qrar_result["ar"]

            analysis = analysis_service.generate_full_analysis(
                reading_score,
                qr_score,
                ar_score,
                writing_score,
            )

            reading_pdf = annotator_service.image_to_pdf_bytes(
                annotator_service.annotate_sheet(
                    reading_result["marked_image"],
                    reading_score.get("questions", []),
                    "Reading",
                    reading_score,
                )
            )
            qr_pdf = annotator_service.image_to_pdf_bytes(
                annotator_service.annotate_sheet(
                    qrar_result["marked_image"],
                    qr_score.get("questions", []),
                    "Quantitative Reasoning",
                    qr_score,
                )
            )
            ar_pdf = annotator_service.image_to_pdf_bytes(
                annotator_service.annotate_sheet(
                    qrar_result["marked_image"],
                    ar_score.get("questions", []),
                    "Abstract Reasoning",
                    ar_score,
                )
            )

            report_pdf = report_service.generate_student_report(
                student_name,
                reading_score,
                qr_score,
                ar_score,
                writing_score,
                analysis,
            )

            results_payload: dict[str, Any] = {
                "student": student_name,
                "writing_score": writing_score,
                "reading": reading_score,
                "quantitative_reasoning": qr_score,
                "abstract_reasoning": ar_score,
                "analysis": analysis,
                "multi_marked": {
                    "reading": reading_result.get("multi_marked", False),
                    "qrar": qrar_result.get("multi_marked", False),
                },
            }

            folder_name = _sanitize_name(student_name)
            base_path = f"{folder_name}/"
            results_zip.writestr(base_path + "report.pdf", report_pdf)
            results_zip.writestr(base_path + "reading_annotated.pdf", reading_pdf)
            results_zip.writestr(base_path + "qr_annotated.pdf", qr_pdf)
            results_zip.writestr(base_path + "ar_annotated.pdf", ar_pdf)
            results_zip.writestr(
                base_path + "results.json",
                json.dumps(results_payload, indent=2).encode("utf-8"),
            )

    except BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sheets upload must be a valid ZIP archive.",
        ) from exc

    output_buffer.seek(0)
    filename = "batch_results.zip"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(output_buffer, media_type="application/zip", headers=headers)
