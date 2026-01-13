"""Batch processing routes."""
from __future__ import annotations

import csv
import logging
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from web.app import templates
from web.config import Settings
from web.dependencies import get_settings, require_configuration
from web.services import AnalysisService, AnnotatorService, MarkingService, ReportService
from web.services.docx_report import DocxReportGenerator
from web.session_store import MarkingConfiguration

logger = logging.getLogger(__name__)

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


@router.get("/manifest-builder")
async def manifest_builder(request: Request):
    """Render the manifest builder page for batch processing."""
    return templates.TemplateResponse(
        "manifest_builder.html",
        {"request": request}
    )


@router.post("/process")
async def process_batch(
    request: Request,
    manifest: UploadFile = File(...),
    sheets_zip: Optional[UploadFile] = File(None),
    settings: Settings = Depends(get_settings),
    config: MarkingConfiguration = Depends(require_configuration),
):
        """Process batch uploads and return a ZIP archive with per-student results (robust, partial success).
        
        Supports two upload modes:
        1. ZIP file containing all image sheets
        2. Multiple individual image files (jpg, jpeg, png)
        """
        from web.services.marker import SubjectResult
        import dataclasses
        empty_ar = SubjectResult(subject_name="AR", score=0, total_questions=0, results=[], marked_image=None, omr_response={})
        _validate_extension(manifest, {".json"})
        
        # Parse form data to get all uploaded files
        form = await request.form()
        
        # Collect all sheets (either from ZIP or individual files)
        sheets_dict: Dict[str, bytes] = {}
        
        # Get all files from sheets_zip field (could be one ZIP or multiple images)
        sheets_files = form.getlist("sheets_zip")
        logger.info(f"Received {len(sheets_files)} file(s) in sheets_zip field")
        
        for file_item in sheets_files:
            # Skip non-file items (form.getlist can return strings)
            if not hasattr(file_item, 'filename') or not hasattr(file_item, 'read'):
                continue
            
            filename = getattr(file_item, 'filename', None)
            if not filename:
                continue
                
            logger.info(f"Processing uploaded file: {filename}")
            
            # Check if it's a ZIP file
            if filename.lower().endswith('.zip'):
                file_bytes = await file_item.read()  # type: ignore
                size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
                if len(file_bytes) > size_limit:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Uploaded ZIP exceeds the allowed size for batch processing.",
                    )
                
                # Extract files from ZIP
                try:
                    sheets_io = io.BytesIO(file_bytes)
                    with ZipFile(sheets_io) as zf:
                        for name in zf.namelist():
                            # Skip directories and hidden files
                            if name.endswith('/') or name.startswith('__MACOSX') or name.startswith('.'):
                                continue
                            # Get just the filename (in case files are in subdirectories)
                            basename = Path(name).name
                            if basename.lower().endswith(('.png', '.jpg', '.jpeg')):
                                sheets_dict[basename] = zf.read(name)
                                # Also store with full path for fallback matching
                                sheets_dict[name] = zf.read(name)
                                logger.info(f"Extracted from ZIP: {basename}")
                except BadZipFile as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Sheets upload must be a valid ZIP archive.",
                    ) from exc
            
            # Check if it's an image file
            elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                content = await file_item.read()  # type: ignore
                sheets_dict[filename] = content
                logger.info(f"Loaded image file: {filename} ({len(content)} bytes)")
        
        if not sheets_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No image files found. Please upload a ZIP file containing images or individual image files.",
            )
        
        logger.info(f"Total sheets loaded: {len(sheets_dict)}, files: {list(sheets_dict.keys())[:10]}...")

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

        marking_service = MarkingService(settings.CONFIG_DIR)
        analysis_service = AnalysisService(config.concept_mapping) if config.has_concept_mapping else None
        docx_generator = DocxReportGenerator() if config.has_concept_mapping else None
        annotator_service = AnnotatorService()

        def _find_file_in_sheets(filename: str, sheets: Dict[str, bytes]) -> Optional[bytes]:
            """Find a file in the sheets dictionary, trying multiple matching strategies."""
            # Exact match
            if filename in sheets:
                return sheets[filename]
            
            # Case-insensitive match
            filename_lower = filename.lower()
            for key, data in sheets.items():
                if key.lower() == filename_lower:
                    return data
            
            # Basename match (in case manifest has full path or vice versa)
            basename = Path(filename).name
            for key, data in sheets.items():
                if Path(key).name.lower() == basename.lower():
                    return data
            
            # Partial match (filename contained in key or key contained in filename)
            for key, data in sheets.items():
                if basename.lower() in key.lower() or Path(key).name.lower() in filename_lower:
                    return data
            
            return None

        def _process_batch_student(student, sheets: Dict[str, bytes]):
            student_name = student["name"]
            writing_score = student["writing_score"]
            reading_file = student["reading_file"]
            qrar_file = student["qrar_file"]
            folder_name = _sanitize_name(student_name)
            base_path = f"{folder_name}/"
            
            logger.info(f"Processing student: {student_name}, reading: {reading_file}, qrar: {qrar_file}")
            
            # Convert answer keys to dicts with proper prefixes
            # Reading: RC1, RC2, ...
            reading_key = {f"RC{i+1}": ans for i, ans in enumerate(config.reading_answers)}
            
            # QR/AR: QR1, QR2, ... + AR1, AR2, ...
            qrar_key = {}
            for i, ans in enumerate(config.qr_answers):
                qrar_key[f"QR{i+1}"] = ans
            for i, ans in enumerate(config.ar_answers):
                qrar_key[f"AR{i+1}"] = ans
            
            # Try to read files and process
            try:
                reading_bytes = _find_file_in_sheets(reading_file, sheets)
                if reading_bytes is None:
                    raise FileNotFoundError(f"Reading file not found: {reading_file}")
                
                qrar_bytes = _find_file_in_sheets(qrar_file, sheets)
                if qrar_bytes is None:
                    raise FileNotFoundError(f"QRAR file not found: {qrar_file}")
                
                logger.info(f"Found files for {student_name}: reading={len(reading_bytes)} bytes, qrar={len(qrar_bytes)} bytes")
                
                reading_result = marking_service.process_single_subject(
                    subject_name="Reading",
                    image_bytes=reading_bytes,
                    answer_key=reading_key,
                    template_filename="aset_reading_template.json",
                )
                logger.info(f"Reading marked for {student_name}: score={reading_result.score}/{reading_result.total_questions}")
                
                qrar_result = marking_service.process_single_subject(
                    subject_name="QR/AR",
                    image_bytes=qrar_bytes,
                    answer_key=qrar_key,
                    template_filename="aset_qrar_template.json",
                )
                logger.info(f"QRAR marked for {student_name}: score={qrar_result.score}/{qrar_result.total_questions}")
                
                # Split QR/AR into separate SubjectResults
                qr_len = len(config.qr_answers)
                ar_len = len(config.ar_answers)
                qr_result = None
                ar_result = None
                
                if qrar_result and hasattr(qrar_result, 'results'):
                    qr_results = qrar_result.results[:qr_len]
                    ar_results = qrar_result.results[qr_len:qr_len+ar_len]
                    
                    # Recalculate scores
                    qr_score = sum(1 for q in qr_results if getattr(q, 'is_correct', False))
                    ar_score = sum(1 for q in ar_results if getattr(q, 'is_correct', False))
                    
                    # Build new SubjectResult objects
                    qr_result = SubjectResult(
                        subject_name="Quantitative Reasoning",
                        score=qr_score,
                        total_questions=qr_len,
                        results=qr_results,
                        omr_response=qrar_result.omr_response,
                        marked_image=qrar_result.marked_image,
                        template=qrar_result.template,
                        clean_image=getattr(qrar_result, 'clean_image', None)
                    )
                    ar_result = SubjectResult(
                        subject_name="Abstract Reasoning",
                        score=ar_score,
                        total_questions=ar_len,
                        results=ar_results,
                        omr_response=qrar_result.omr_response,
                        marked_image=qrar_result.marked_image,
                        template=qrar_result.template,
                        clean_image=getattr(qrar_result, 'clean_image', None)
                    )
                
                # Annotate sheets
                reading_img = annotator_service.annotate_sheet(reading_result)
                qrar_img = annotator_service.annotate_sheet(qrar_result)
                reading_pdf = annotator_service.image_to_pdf_bytes(reading_img)
                qrar_pdf = annotator_service.image_to_pdf_bytes(qrar_img)
                
                artifacts = [
                    (base_path + f"{folder_name}_Reading_Marked.pdf", reading_pdf),
                    (base_path + f"{folder_name}_QRAR_Marked.pdf", qrar_pdf),
                ]
                
                # Generate analysis and report only if concept mapping exists
                if analysis_service and docx_generator and qr_result and ar_result:
                    full_analysis = analysis_service.generate_full_analysis(
                        reading_result,
                        qr_result,
                        ar_result,
                    )
                    # Generate Word document report using docxtpl
                    docx_bytes = docx_generator.generate_report_bytes(
                        student_data={
                            'name': student_name,
                            'writing_score': writing_score,
                            'reading_score': reading_result.score,
                            'reading_total': len(config.reading_answers),
                            'qr_score': qr_result.score,
                            'qr_total': len(config.qr_answers),
                            'ar_score': ar_result.score,
                            'ar_total': len(config.ar_answers),
                        },
                        flow_type='batch',
                        analysis=full_analysis,
                    )
                    results_json = json.dumps(dataclasses.asdict(full_analysis), indent=2).encode("utf-8")
                    artifacts.extend([
                        (base_path + f"{folder_name}_Report.docx", docx_bytes),
                        (base_path + f"{folder_name}_results.json", results_json),
                    ])
                
                return {
                    "status": "Success",
                    "student_name": student_name,
                    "writing_score": writing_score,
                    "reading_score": getattr(reading_result, 'score', ''),
                    "qr_score": getattr(qr_result, 'score', '') if qr_result else '',
                    "ar_score": getattr(ar_result, 'score', '') if ar_result else '',
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
        detailed_rows = []
        
        # Get totals from config for percentage calculations
        reading_total = len(config.reading_answers) if config.reading_answers else 35
        qr_total = len(config.qr_answers) if config.qr_answers else 35
        ar_total = len(config.ar_answers) if config.ar_answers else 35
        writing_total = 50  # Standard writing total
        
        with ZipFile(output_buffer, "w") as results_zip:
            for student in manifest_json["students"]:
                result = _process_batch_student(student, sheets_dict)
                logger.info(f"Student {result['student_name']}: {result['status']} - {result['notes']}")
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
                
                # Prepare detailed row with percentages and standard score
                if result["status"] == "Success":
                    reading_score = float(result["reading_score"]) if result["reading_score"] else 0.0
                    writing_score = float(result["writing_score"]) if result["writing_score"] else 0.0
                    qr_score = float(result["qr_score"]) if result["qr_score"] else 0.0
                    ar_score = float(result["ar_score"]) if result["ar_score"] else 0.0
                    
                    # Calculate percentages
                    reading_pct = round((reading_score / reading_total * 100), 2) if reading_total > 0 else 0.0
                    qr_pct = round((qr_score / qr_total * 100), 2) if qr_total > 0 else 0.0
                    ar_pct = round((ar_score / ar_total * 100), 2) if ar_total > 0 else 0.0
                    
                    # Calculate total standard score (sum of raw scores)
                    total_standard_score = reading_score + writing_score + qr_score + ar_score
                else:
                    # Error case: fill with zeros
                    reading_score = 0.0
                    writing_score = 0.0
                    qr_score = 0.0
                    ar_score = 0.0
                    reading_pct = 0.0
                    qr_pct = 0.0
                    ar_pct = 0.0
                    total_standard_score = 0.0
                
                detailed_rows.append([
                    result["student_name"],
                    reading_score,
                    reading_pct,
                    writing_score,
                    qr_score,
                    qr_pct,
                    ar_score,
                    ar_pct,
                    total_standard_score
                ])
            
            # Calculate batch averages for detailed report
            if detailed_rows:
                num_students = len(detailed_rows)
                
                # Sum each numeric column (skip student name at index 0)
                col_sums = [0.0] * 8  # 8 numeric columns
                for row in detailed_rows:
                    for i in range(1, 9):  # Columns 1-8 are numeric
                        col_sums[i-1] += row[i]
                
                # Calculate averages
                col_averages = [round(s / num_students, 2) for s in col_sums]
                
                # Create averages row
                averages_row = ["Batch Averages"] + col_averages
                detailed_rows.append(averages_row)
            
            # Write detailed_batch_report.csv
            detailed_csv_buffer = io.StringIO()
            detailed_writer = csv.writer(detailed_csv_buffer)
            detailed_writer.writerow([
                "Student Name/Test Time",
                "Reading Score (/35)",
                "Reading %",
                "Writing Score (/50)",
                "QR Score (/35)",
                "QR %",
                "AR score (/35)",
                "AR %",
                "Total Standard Score (/400)"
            ])
            detailed_writer.writerows(detailed_rows)
            results_zip.writestr("detailed_batch_report.csv", detailed_csv_buffer.getvalue())
            
            # Write batch_summary.csv (keep existing for backwards compatibility)
            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)
            writer.writerow(["Student Name", "Status", "Writing Score", "Reading Score", "QR Score", "AR Score", "Notes"])
            writer.writerows(summary_rows)
            results_zip.writestr("batch_summary.csv", csv_buffer.getvalue())

        output_buffer.seek(0)
        filename = "batch_results.zip"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(output_buffer, media_type="application/zip", headers=headers)
