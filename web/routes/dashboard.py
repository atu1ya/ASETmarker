"""Dashboard and configuration routes."""
from __future__ import annotations

import csv
import json
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


def parse_answer_key(content: str) -> list[str]:
    """Parse answer keys provided either as newline separated values or CSV."""
    cleaned = content.strip()
    if not cleaned:
        return []

    if "," in cleaned:
        reader = csv.reader(StringIO(cleaned))
        answers: list[str] = []
        for row in reader:
            if not row:
                continue
            answer = row[-1].strip()
            if answer:
                answers.append(answer)
        return answers

    return [line.strip() for line in cleaned.splitlines() if line.strip()]


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
            "qrar_questions": 0,
            "subjects_mapped": [],
            "uploaded_at": None,
        }

    return {
        "configured": True,
        "reading_questions": len(config.reading_answers),
        "qrar_questions": len(config.qrar_answers),
        "subjects_mapped": [
            subject for subject in config.concept_mapping.keys() if not subject.startswith("_")
        ],
        "uploaded_at": config.uploaded_at,
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
    reading_answers: UploadFile = File(...),
    qrar_answers: UploadFile = File(...),
    concept_mapping: UploadFile = File(...),
):
    """Upload and store marking configuration for the current session."""
    def _validate_extension(upload: UploadFile, allowed: set[str]) -> None:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type for {upload.filename}",
            )

    _validate_extension(reading_answers, ALLOWED_TEXT_EXTENSIONS)
    _validate_extension(qrar_answers, ALLOWED_TEXT_EXTENSIONS)
    _validate_extension(concept_mapping, {".json"})

    reading_content = (await reading_answers.read()).decode("utf-8", errors="ignore")
    qrar_content = (await qrar_answers.read()).decode("utf-8", errors="ignore")
    concept_content = (await concept_mapping.read()).decode("utf-8", errors="ignore")

    reading_list = parse_answer_key(reading_content)
    qrar_list = parse_answer_key(qrar_content)

    if not reading_list or not qrar_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer keys must contain at least one entry.",
        )

    try:
        concepts = json.loads(concept_content)
    except json.JSONDecodeError as exc:  # pragma: no cover - simple parse failure
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
        qrar_answers=qrar_list,
        concept_mapping=concepts,
        uploaded_at=datetime.utcnow(),
    )
    config_store.set(session_token, config)

    summary = get_configuration_status(session_token)
    return JSONResponse({"status": "success", "summary": summary})
