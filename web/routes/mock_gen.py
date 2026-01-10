"""Mock report generation routes."""
import io
from pathlib import Path
from zipfile import ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from web.app import templates
from web.config import Settings
from web.dependencies import get_current_session, get_settings
from web.services.mock_report_service import MockReportService
from web.services.docx_report import DocxReportGenerator

router = APIRouter()


def _pop_flash_messages(request: Request) -> list[dict[str, str]]:
    messages = request.session.get("flash_messages", [])
    request.session["flash_messages"] = []
    return messages


@router.get("/mock-report")
async def mock_report_page(
    request: Request,
    session_token: str = Depends(get_current_session),
):
    """Render the mock report upload page."""
    return templates.TemplateResponse(
        "mock_report_upload.html",
        {
            "request": request,
            "messages": _pop_flash_messages(request),
        },
    )


@router.post("/mock-report/generate")
async def generate_mock_reports(
    request: Request,
    csv_file: UploadFile = File(...),
    session_token: str = Depends(get_current_session),
    settings: Settings = Depends(get_settings),
):
    """Process the CSV and generate mock reports using docxtpl Word templates."""
    # Validate file type
    if not csv_file.filename or not csv_file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file.",
        )
    
    # Read CSV file
    size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    csv_bytes = await csv_file.read()
    
    if len(csv_bytes) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file exceeds the maximum allowed size.",
        )
    
    # Process the CSV and generate reports
    try:
        mock_service = MockReportService()
        students_data = mock_service.parse_csv(csv_bytes)
        
        if not students_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid student data found in CSV.",
            )
        
        # Initialize DocX report generator
        docx_generator = DocxReportGenerator()
        
        # Generate ZIP archive with Word reports and email templates
        zip_buffer = io.BytesIO()
        
        with ZipFile(zip_buffer, "w") as bundle:
            for student in students_data:
                # Generate Word report using docxtpl (flow_type='mock')
                docx_bytes = docx_generator.generate_report_bytes(
                    student_data=student,
                    flow_type='mock',
                )
                safe_name = student['name'].replace(' ', '_')
                bundle.writestr(f"{safe_name}_Report.docx", docx_bytes)
        
        zip_buffer.seek(0)
        filename = "Mock_Reports.zip"
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
        return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report template not found: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}",
        )
