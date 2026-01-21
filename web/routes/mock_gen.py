"""Mock report generation routes."""
import io
from pathlib import Path
from zipfile import ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from web.app import templates
from web.config import Settings
from web.dependencies import get_current_session, get_settings
from web.services.mock_report_service import MockReportService, READING_CONCEPTS, QR_CONCEPTS
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


ALLOWED_DATA_EXTENSIONS = {'.csv', '.xlsx', '.xls'}


@router.post("/mock-report/generate")
async def generate_mock_reports(
    request: Request,
    csv_file: UploadFile = File(...),
    session_token: str = Depends(get_current_session),
    settings: Settings = Depends(get_settings),
):
    """Process the CSV/Excel file and generate mock reports using docxtpl Word templates."""
    # Validate file type
    if not csv_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded.",
        )
    
    file_ext = Path(csv_file.filename).suffix.lower()
    if file_ext not in ALLOWED_DATA_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV or Excel file (.csv, .xlsx, .xls).",
        )
    
    # Read file
    size_limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    file_bytes = await csv_file.read()
    
    if len(file_bytes) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds the maximum allowed size.",
        )
    
    # Process the file and generate reports
    try:
        mock_service = MockReportService()
        # Parse based on file type
        if file_ext == '.csv':
            students_data = mock_service.parse_csv(file_bytes)
        else:
            students_data = mock_service.parse_excel(file_bytes)
        
        if not students_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid student data found in CSV.",
            )
        
        # Convert concept dictionaries to the expected format
        # Format: {'Reading': {'concept_name': 'q1, q2, q3'}, 'Quantitative Reasoning': {...}}
        concept_mapping = {
            'Reading': {concept: ', '.join(questions) for concept, questions in READING_CONCEPTS.items()},
            'Quantitative Reasoning': {concept: ', '.join(questions) for concept, questions in QR_CONCEPTS.items()}
        }
        
        # Initialize DocX report generator with concept mapping
        docx_generator = DocxReportGenerator(concept_mapping=concept_mapping)
        
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
                
                # Create folder structure: StudentName/StudentName_Report.docx
                bundle.writestr(f"{safe_name}/{safe_name}_Report.docx", docx_bytes)
                
                # Generate performance chart as PNG
                chart_bytes = docx_generator.generate_chart_bytes(
                    student_data=student,
                    flow_type='mock',
                )
                # Store chart in same student folder
                bundle.writestr(f"{safe_name}/{safe_name}_Graph.png", chart_bytes)
        
        zip_buffer.seek(0)
        filename = "Mock_Reports.zip"
        content_length = str(zip_buffer.getbuffer().nbytes)
        headers = {
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": content_length
        }
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
