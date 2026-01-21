"""Dashboard and configuration routes."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse

from web.app import templates
from web.dependencies import get_current_session
from web.session_store import MarkingConfiguration, config_store

router = APIRouter()

ALLOWED_TEXT_EXTENSIONS = {".txt", ".csv"}


def _pop_flash_messages(request: Request) -> list[dict[str, str]]:
    messages = request.session.get("flash_messages", [])
    request.session["flash_messages"] = []
    return messages


def _is_header_row(row: list[str]) -> bool:
    """Check if a CSV row appears to be a header row rather than data."""
    if not row:
        return False
    first_cell = row[0].strip().lower()
    # Common header words to skip
    header_keywords = {'question', 'q', 'number', 'no', 'no.', '#', 'item', 'qn', 'qno'}
    # Check if first cell is a header keyword (but not q1, q2, etc.)
    if first_cell in header_keywords:
        return True
    # Check if second column (answer column) contains header-like text
    if len(row) > 1:
        second_cell = row[1].strip().lower()
        answer_headers = {'answer', 'ans', 'correct', 'key', 'response', 'correct answer'}
        if second_cell in answer_headers:
            return True
    return False


def _is_question_row(row: list[str]) -> bool:
    """Check if a CSV row looks like a question row (e.g., q1, 1, Q1, etc.)."""
    if not row:
        return False
    first_cell = row[0].strip().lower()
    # Match patterns like q1, q2, 1, 2, rc1, ar1, qr1, etc.
    return bool(re.match(r'^(q|rc|ar|qr)?\d+$', first_cell))


def parse_answer_key(content: str) -> list[str]:
    """Parse answer keys provided either as newline separated values or CSV.
    
    Supports CSV files with optional header rows (e.g., 'Question,Answer').
    Header rows are automatically skipped.
    """
    cleaned = content.strip()
    if not cleaned:
        return []

    if "," in cleaned:
        reader = csv.reader(StringIO(cleaned))
        answers: list[str] = []
        found_data = False
        for row in reader:
            if not row:
                continue
            # Skip header rows until we find actual data
            if not found_data:
                if _is_header_row(row):
                    continue
                # Check if this looks like a question row to start parsing
                if _is_question_row(row) or len(row) >= 2:
                    found_data = True
            if found_data:
                answer = row[-1].strip()
                if answer:
                    answers.append(answer)
        return answers

    # For non-CSV (newline separated), skip header-like lines
    lines = cleaned.splitlines()
    answers = []
    for line in lines:
        stripped = line.strip().lower()
        if not stripped:
            continue
        # Skip common header words for plain text files
        if stripped in {'answer', 'answers', 'key', 'answer key', 'correct', 'correct answers'}:
            continue
        answers.append(line.strip())
    return answers


def validate_concept_mapping(concepts: dict) -> list[str]:
    """Validate the uploaded concept mapping structure."""
    errors: list[str] = []
    if not isinstance(concepts, dict):
        return ["Concept mapping must be a JSON object."]

    for subject, areas in concepts.items():
        if subject.startswith("_"):
            continue
        if not isinstance(areas, dict):
            errors.append(f"Subject '{subject}' must map to an object of areas.")
            continue
        for area, questions in areas.items():
            if not isinstance(questions, list):
                errors.append(
                    f"Area '{area}' in subject '{subject}' must be a list of question identifiers."
                )
                continue
            for question in questions:
                if not isinstance(question, str) or not question.strip():
                    errors.append(
                        f"Area '{area}' in subject '{subject}' contains an invalid question identifier."
                    )
    return errors


def get_configuration_status(session_token: str) -> dict:
    """Return summary information about the configuration for a session."""
    config = config_store.get(session_token)
    if not config or not config.is_configured:
        return {
            "configured": False,
            "reading_questions": 0,
            "qr_questions": 0,
            "ar_questions": 0,
            "subjects_mapped": [],
            "uploaded_at": None,
        }

    return {
        "configured": True,
        "reading_questions": len(config.reading_answers),
        "qr_questions": len(config.qr_answers),
        "ar_questions": len(config.ar_answers),
        "subjects_mapped": [
            subject for subject in config.concept_mapping.keys() if not subject.startswith("_")
        ],
        "uploaded_at": config.uploaded_at.isoformat() if config.uploaded_at else None,
        "has_concept_mapping": config.has_concept_mapping,
    }


@router.get("/")
async def dashboard_home(request: Request, session_token: str = Depends(get_current_session)):
    """Render the main dashboard."""
    status_summary = get_configuration_status(session_token)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "config_status": status_summary,
            "messages": _pop_flash_messages(request),
        },
    )


@router.get("/dashboard")
async def dashboard_alias():
    """Redirect /dashboard to the root dashboard."""
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/configure")
async def configure_marking(
    session_token: str = Depends(get_current_session),
    reading_answers: UploadFile = File(None),
    qr_answers: UploadFile = File(None),
    ar_answers: UploadFile = File(None),
    concept_mapping: UploadFile = File(None),
):
    """Upload and store marking configuration for the current session."""
    def _validate_extension(upload: UploadFile, allowed: set[str]) -> None:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type for {upload.filename}",
            )

    reading_list = []
    qr_list = []
    ar_list = []

    if reading_answers and reading_answers.filename:
        _validate_extension(reading_answers, ALLOWED_TEXT_EXTENSIONS)
        reading_content = (await reading_answers.read()).decode("utf-8", errors="ignore")
        reading_list = parse_answer_key(reading_content)
        if not reading_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reading answer key must contain at least one entry.",
            )

    if qr_answers and qr_answers.filename:
        _validate_extension(qr_answers, ALLOWED_TEXT_EXTENSIONS)
        qr_content = (await qr_answers.read()).decode("utf-8", errors="ignore")
        qr_list = parse_answer_key(qr_content)
        if not qr_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR answer key must contain at least one entry.",
            )

    if ar_answers and ar_answers.filename:
        _validate_extension(ar_answers, ALLOWED_TEXT_EXTENSIONS)
        ar_content = (await ar_answers.read()).decode("utf-8", errors="ignore")
        ar_list = parse_answer_key(ar_content)
        if not ar_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AR answer key must contain at least one entry.",
            )

    if not reading_list and not qr_list and not ar_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one answer key (Reading, QR, or AR) must be uploaded.",
        )

    concepts = {}
    if concept_mapping and concept_mapping.filename:
        _validate_extension(concept_mapping, {".json"})
        concept_content = (await concept_mapping.read()).decode("utf-8", errors="ignore")
        try:
            concepts = json.loads(concept_content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Concept mapping must be valid JSON.",
            ) from exc

        validation_errors = validate_concept_mapping(concepts)
        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="; ".join(validation_errors),
            )

    config = MarkingConfiguration(
        reading_answers=reading_list,
        qr_answers=qr_list,
        ar_answers=ar_list,
        concept_mapping=concepts,
        uploaded_at=datetime.utcnow(),
    )
    config_store.set(session_token, config)

    summary = get_configuration_status(session_token)
    return JSONResponse({"status": "success", "summary": summary})
