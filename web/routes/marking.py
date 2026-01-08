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
        "qr_questions": len(config.qr_answers),
        "ar_questions": len(config.ar_answers),
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
    writing_score: int = Form(0, ge=0, le=100),
    reading_sheet: UploadFile = File(None),
    qrar_sheet: UploadFile = File(None),
    generate_report: bool = Form(False),
    settings: Settings = Depends(get_settings),
    config: MarkingConfiguration = Depends(require_configuration),
):
    """Process single student uploads and return a ZIP archive of results."""
    from web.services.marker import SubjectResult
    
    # Check that at least one file is provided
    if not reading_sheet and not qrar_sheet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sheet (Reading or QR/AR) must be uploaded.",
        )
    
    empty_ar = SubjectResult(subject_name="AR", score=0, total_questions=0, results=[], marked_image=None, omr_response={})

    # Validate file types
    allowed = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}
    if reading_sheet and reading_sheet.filename:
        _validate_upload(reading_sheet, allowed)
    if qrar_sheet and qrar_sheet.filename:
        _validate_upload(qrar_sheet, allowed)

    # Read files into memory
    size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    reading_bytes = None
    qrar_bytes = None
    
    if reading_sheet and reading_sheet.filename:
        reading_bytes = await reading_sheet.read()
        if len(reading_bytes) > size_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reading sheet exceeds the maximum allowed size.",
            )
    
    if qrar_sheet and qrar_sheet.filename:
        qrar_bytes = await qrar_sheet.read()
        if len(qrar_bytes) > size_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR/AR sheet exceeds the maximum allowed size.",
            )

    # Marking
    marking_service = MarkingService(settings.CONFIG_DIR)
    reading_result = None
    qrar_result = None
    
    try:
        if reading_bytes:
            reading_key = {str(i+1): ans for i, ans in enumerate(config.reading_answers)}
            reading_result = marking_service.process_single_subject(
                subject_name="Reading",
                image_bytes=reading_bytes,
                answer_key=reading_key,
                template_filename="aset_reading_template.json",
            )
        
        if qrar_bytes:
            # Combine QR and AR answers for the combined sheet
            combined_answers = config.qr_answers + config.ar_answers
            qrar_key = {str(i+1): ans for i, ans in enumerate(combined_answers)}
            qrar_result = marking_service.process_single_subject(
                subject_name="QR/AR",
                image_bytes=qrar_bytes,
                answer_key=qrar_key,
                template_filename="aset_qrar_template.json",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Marking failed: {str(e)}",
        )

    # Artifact Generation
    annotator_service = AnnotatorService()
    folder_name = _sanitize_name(student_name)
    zip_buffer = io.BytesIO()
    
    with ZipFile(zip_buffer, "w") as bundle:
        # Add marked sheets for files that were processed
        if reading_result:
            reading_img = annotator_service.annotate_sheet(reading_result)
            reading_pdf = annotator_service.image_to_pdf_bytes(reading_img)
            bundle.writestr(f"{folder_name}_Reading_Marked.pdf", reading_pdf)
        
        if qrar_result:
            qrar_img = annotator_service.annotate_sheet(qrar_result)
            qrar_pdf = annotator_service.image_to_pdf_bytes(qrar_img)
            bundle.writestr(f"{folder_name}_QRAR_Marked.pdf", qrar_pdf)
        
        # Generate report and analysis only if requested and both files provided
        if generate_report and reading_result and qrar_result:
            analysis_service = AnalysisService(config.concept_mapping)
            full_analysis = analysis_service.generate_full_analysis(
                reading_result,
                qrar_result,
                empty_ar,
            )
            report_service = ReportService()
            report_pdf = report_service.generate_student_report(full_analysis, student_name)
            bundle.writestr(f"{folder_name}_Report.pdf", report_pdf)
            
            # JSON results
            import dataclasses
            results_json = json.dumps(dataclasses.asdict(full_analysis), indent=2).encode("utf-8")
            bundle.writestr(f"{folder_name}_results.json", results_json)

    zip_buffer.seek(0)
    filename = f"{folder_name}_results.zip"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
