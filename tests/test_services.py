"""Service layer tests for stub implementations."""
from pathlib import Path

import numpy as np

from web.services import AnalysisService, AnnotatorService, MarkingService, ReportService


def test_marking_service_stub_outputs(tmp_path):
    config_dir = tmp_path
    service = MarkingService(config_dir)
    answer_key = ["A", "B", "C"]
    reading = service.mark_reading_sheet(b"bytes", answer_key)
    qrar = service.mark_qrar_sheet(b"bytes", answer_key)

    assert reading["results"]["correct"] == len(answer_key)
    assert reading["marked_image"].shape == (100, 100)
    assert qrar["qr"]["total"] == min(25, len(answer_key))


def test_analysis_service_stub():
    mapping = {
        "Reading": {
            "Area1": ["q1", "q2"],
            "Area2": ["q3"],
        },
        "_instructions": "ignore",
    }
    service = AnalysisService(mapping)
    results = service.analyze_performance(
        "Reading",
        [
            {"question": "q1", "is_correct": True},
            {"question": "q2", "is_correct": False},
            {"question": "q3", "is_correct": True},
        ],
    )

    assert "Area1" in results["improvements"]
    assert "Area2" in results["strengths"]


def test_report_service_stub(tmp_path):
    from web.services.analysis import FullAnalysis, LearningAreaResult
    
    assets_dir = tmp_path
    service = ReportService(assets_dir)
    
    # Create a minimal FullAnalysis object
    analysis = FullAnalysis(
        subject_areas={
            "Reading": [
                LearningAreaResult(area="Comprehension", correct=5, total=10, percentage=50.0, status="Needs improvement"),
            ],
            "Quantitative Reasoning": [
                LearningAreaResult(area="Number Patterns", correct=8, total=10, percentage=80.0, status="Done well"),
            ],
            "Abstract Reasoning": [
                LearningAreaResult(area="Pattern Recognition", correct=7, total=10, percentage=70.0, status="Done well"),
            ],
        },
        summary={}
    )
    
    pdf_bytes = service.generate_student_report(
        analysis,
        student_name="Test Student",
        writing_score=85,
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_annotator_service_stub():
    service = AnnotatorService()
    image = np.zeros((10, 10), dtype=np.uint8)
    annotated = service.annotate_sheet(image, [], "Reading", {})
    assert annotated is image
    pdf_bytes = service.image_to_pdf_bytes(image)
    assert pdf_bytes.startswith(b"%PDF")
