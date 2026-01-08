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
    from web.services.marker import SubjectResult
    empty_ar = SubjectResult(subject_name="AR", score=0, total_questions=0, results=[], marked_image=None, omr_response={})

    # Validate file types
    allowed = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}
    _validate_upload(reading_sheet, allowed)
    _validate_upload(qrar_sheet, allowed)

    # Read files into memory
    reading_bytes = await reading_sheet.read()
    qrar_bytes = await qrar_sheet.read()
    size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(reading_bytes) > size_limit or len(qrar_bytes) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded files exceed the maximum allowed size.",
        )

    # Marking

    marking_service = MarkingService(settings.CONFIG_DIR)
    # Convert answer keys to dicts (label: answer)
    reading_key = {str(i+1): ans for i, ans in enumerate(config.reading_answers)}
    qrar_key = {str(i+1): ans for i, ans in enumerate(config.qrar_answers)}

    reading_result = marking_service.process_single_subject(
        subject_name="Reading",
        image_bytes=reading_bytes,
        answer_key=reading_key,
        template_filename="config/aset_reading_template.json",
    )
    qrar_result = marking_service.process_single_subject(
        subject_name="QR/AR",
        image_bytes=qrar_bytes,
        answer_key=qrar_key,
        template_filename="config/aset_qrar_template.json",
    )

    # Analysis
    analysis_service = AnalysisService(config.concept_mapping)
    full_analysis = analysis_service.generate_full_analysis(
        reading_result,
        qrar_result,
        empty_ar,
    )

    # Artifact Generation

    report_service = ReportService()
    annotator_service = AnnotatorService()
    report_pdf = report_service.generate_student_report(full_analysis)
    reading_img = annotator_service.annotate_sheet(reading_result)
    qrar_img = annotator_service.annotate_sheet(qrar_result)
    reading_pdf = annotator_service.image_to_pdf_bytes(reading_img)
    qrar_pdf = annotator_service.image_to_pdf_bytes(qrar_img)

    # JSON results
    import dataclasses
    results_json = json.dumps(dataclasses.asdict(full_analysis), indent=2).encode("utf-8")

    # ZIP Packaging
    folder_name = _sanitize_name(student_name)
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as bundle:
        bundle.writestr(f"{folder_name}_Report.pdf", report_pdf)
        bundle.writestr(f"{folder_name}_Reading_Marked.pdf", reading_pdf)
        bundle.writestr(f"{folder_name}_QRAR_Marked.pdf", qrar_pdf)
        bundle.writestr(f"{folder_name}_results.json", results_json)

    zip_buffer.seek(0)
    filename = f"{folder_name}_results.zip"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
