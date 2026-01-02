"""Single student marking routes."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from web.app import templates
from web.config import Settings
from web.dependencies import get_current_session, get_marking_config, get_settings, require_configuration
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


def _validate_upload(file: UploadFile, allowed_extensions: set[str]) -> None:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{file.filename}' must be one of: {', '.join(sorted(allowed_extensions))}.",
        )


@router.get("/single")
async def single_marking_page(
    request: Request,
    session_token: str = Depends(get_current_session),
    config: MarkingConfiguration = Depends(require_configuration),
):
    """Render the single student marking page."""
    summary = {
        "reading_questions": len(config.reading_answers),
        "qrar_questions": len(config.qrar_answers),
        "subjects": [
            subject for subject in config.concept_mapping.keys() if not subject.startswith("_")
        ],
    }
    return templates.TemplateResponse(
        "single.html",
        {
            "request": request,
            "config_summary": summary,
            "messages": _pop_flash_messages(request),
        },
    )


@router.post("/single/process")
async def process_single_student(
    request: Request,
    student_name: str = Form(...),
    writing_score: int = Form(..., ge=0, le=100),
    reading_sheet: UploadFile = File(...),
    qrar_sheet: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    config: MarkingConfiguration = Depends(require_configuration),
):
    """Process single student uploads and return a ZIP archive of results."""
    allowed = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}
    _validate_upload(reading_sheet, allowed)
    _validate_upload(qrar_sheet, allowed)

    reading_bytes = await reading_sheet.read()
    qrar_bytes = await qrar_sheet.read()

    size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(reading_bytes) > size_limit or len(qrar_bytes) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded files exceed the maximum allowed size.",
        )

    marking_service = MarkingService(settings.CONFIG_DIR)
    analysis_service = AnalysisService(config.concept_mapping)
    report_service = ReportService(settings.ASSETS_DIR)
    annotator_service = AnnotatorService()

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
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as bundle:
        bundle.writestr(f"{folder_name}/report.pdf", report_pdf)
        bundle.writestr(f"{folder_name}/reading_annotated.pdf", reading_pdf)
        bundle.writestr(f"{folder_name}/qr_annotated.pdf", qr_pdf)
        bundle.writestr(f"{folder_name}/ar_annotated.pdf", ar_pdf)
        bundle.writestr(
            f"{folder_name}/results.json",
            json.dumps(results_payload, indent=2).encode("utf-8"),
        )

    zip_buffer.seek(0)
    filename = f"{folder_name}_results.zip"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
