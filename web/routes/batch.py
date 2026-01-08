"""Batch processing routes."""
from __future__ import annotations

import csv

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
        "qr_questions": len(config.qr_answers),
        "ar_questions": len(config.ar_answers),
        "subjects": [
            subject for subject in config.concept_mapping.keys() if not subject.startswith("_")
        ],
        "has_concept_mapping": config.has_concept_mapping,
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
        """Process batch uploads and return a ZIP archive with per-student results (robust, partial success)."""
        from web.services.marker import SubjectResult
        import dataclasses
        empty_ar = SubjectResult(subject_name="AR", score=0, total_questions=0, results=[], marked_image=None, omr_response={})
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
        analysis_service = AnalysisService(config.concept_mapping) if config.has_concept_mapping else None
        report_service = ReportService() if config.has_concept_mapping else None
        annotator_service = AnnotatorService()

        def _process_batch_student(student, sheets_archive_ctx):
            student_name = student["name"]
            writing_score = student["writing_score"]
            reading_file = student["reading_file"]
            qrar_file = student["qrar_file"]
            folder_name = _sanitize_name(student_name)
            base_path = f"{folder_name}/"
            # Convert answer keys to dicts (label: answer)
            reading_key = {str(i+1): ans for i, ans in enumerate(config.reading_answers)}
            # Combine QR and AR answers for the combined sheet
            combined_answers = config.qr_answers + config.ar_answers
            qrar_key = {str(i+1): ans for i, ans in enumerate(combined_answers)}
            # Try to read files and process
            try:
                reading_bytes = sheets_archive_ctx.read(reading_file)
                qrar_bytes = sheets_archive_ctx.read(qrar_file)
                reading_result = marking_service.process_single_subject(
                    subject_name="Reading",
                    image_bytes=reading_bytes,
                    answer_key=reading_key,
                    template_filename="aset_reading_template.json",
                )
                qrar_result = marking_service.process_single_subject(
                    subject_name="QR/AR",
                    image_bytes=qrar_bytes,
                    answer_key=qrar_key,
                    template_filename="aset_qrar_template.json",
                )
                
                # Annotate sheets
                reading_img = annotator_service.annotate_sheet(reading_result)
                qrar_img = annotator_service.annotate_sheet(qrar_result)
                reading_pdf = annotator_service.image_to_pdf_bytes(reading_img)
                qrar_pdf = annotator_service.image_to_pdf_bytes(qrar_img)
                
                artifacts = [
                    (base_path + "Reading_Marked.pdf", reading_pdf),
                    (base_path + "QRAR_Marked.pdf", qrar_pdf),
                ]
                
                # Generate analysis and report only if concept mapping exists
                if analysis_service and report_service:
                    full_analysis = analysis_service.generate_full_analysis(
                        reading_result,
                        qrar_result,
                        empty_ar,
                    )
                    report_pdf = report_service.generate_student_report(full_analysis)
                    results_json = json.dumps(dataclasses.asdict(full_analysis), indent=2).encode("utf-8")
                    artifacts.extend([
                        (base_path + "Report.pdf", report_pdf),
                        (base_path + "results.json", results_json),
                    ])
                return {
                    "status": "Success",
                    "student_name": student_name,
                    "writing_score": writing_score,
                    "reading_score": getattr(reading_result, 'score', ''),
                    "qr_score": getattr(qrar_result, 'score', ''),
                    "ar_score": '',
                    "notes": '',
                    "artifacts": artifacts,
                }
            except Exception as e:
                return {
                    "status": "Error",
                    "student_name": student_name,
                    "writing_score": writing_score,
                    "reading_score": '',
                    "qr_score": '',
                    "ar_score": '',
                    "notes": str(e),
                    "artifacts": []
                }

        output_buffer = io.BytesIO()
        summary_rows = []
        try:
            sheets_io = io.BytesIO(sheets_bytes)
            with ZipFile(sheets_io) as sheets_archive_ctx, ZipFile(output_buffer, "w") as results_zip:
                for student in manifest_json["students"]:
                    result = _process_batch_student(student, sheets_archive_ctx)
                    # Write artifacts if success
                    for fname, data in result["artifacts"]:
                        results_zip.writestr(fname, data)
                    # Prepare summary row
                    summary_rows.append([
                        result["student_name"],
                        result["status"],
                        result["writing_score"],
                        result["reading_score"],
                        result["qr_score"],
                        result["ar_score"],
                        result["notes"]
                    ])
                # Write batch_summary.csv
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(["Student Name", "Status", "Writing Score", "Reading Score", "QR Score", "AR Score", "Notes"])
                writer.writerows(summary_rows)
                results_zip.writestr("batch_summary.csv", csv_buffer.getvalue())
        except BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sheets upload must be a valid ZIP archive.",
            ) from exc

        output_buffer.seek(0)
        filename = "batch_results.zip"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(output_buffer, media_type="application/zip", headers=headers)
