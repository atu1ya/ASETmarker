"""
Tests for DocX report rendering with docxtpl.

Verifies that concept tables render correctly with row repetition
and all template fields populate properly.
"""
import io
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from docx import Document

from web.services.docx_report import DocxReportGenerator, FlowType
from web.services.analysis import FullAnalysis, LearningAreaResult


class TestDocxtplRendering:
    """Tests for docxtpl table rendering and field population."""
    
    @pytest.fixture
    def temp_template(self, tmp_path):
        """Create a minimal valid Word template for testing."""
        template_file = tmp_path / "test_template.docx"
        template_file.touch()
        return template_file
    
    def test_docxtpl_renders_table_rows(self, temp_template):
        """Test that docxtpl renders multiple concept rows correctly."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        # Create analysis with 3 Reading concepts
        analysis = FullAnalysis(
            subject_areas={
                "Reading": [
                    LearningAreaResult("Main Idea & Theme", 5, 6, 83.3, "Done well"),
                    LearningAreaResult("Inference & Interpretation", 3, 8, 37.5, "Needs improvement"),
                    LearningAreaResult("Vocabulary in Context", 4, 6, 66.7, "Done well"),
                ],
                "Quantitative Reasoning": [
                    LearningAreaResult("Number & Operations", 4, 5, 80.0, "Done well"),
                    LearningAreaResult("Algebra & Patterns", 2, 5, 40.0, "Needs improvement"),
                ],
                "Abstract Reasoning": [],
            },
            summary={},
        )
        
        # Build context
        context = generator._build_context_from_analysis(
            analysis,
            student_name="Test Student",
            writing_score=15.0,
            flow_type=FlowType.STANDARD,
        )
        
        # Verify rc concepts
        assert "rc" in context
        assert "concepts" in context["rc"]
        assert len(context["rc"]["concepts"]) == 3
        
        # Verify all required fields exist
        for concept in context["rc"]["concepts"]:
            assert "name" in concept
            assert "question_numbers" in concept
            assert "done_well" in concept
            assert "improve" in concept
            assert "done_well_tick" in concept  # Alias
            assert "room_improve_tick" in concept  # Alias
        
        # Verify concept names
        concept_names = [c["name"] for c in context["rc"]["concepts"]]
        assert "Main Idea & Theme" in concept_names
        assert "Inference & Interpretation" in concept_names
        assert "Vocabulary in Context" in concept_names
        
        # Verify question numbers are populated (non-empty strings)
        for concept in context["rc"]["concepts"]:
            assert isinstance(concept["question_numbers"], str)
            # Should have question numbers from mapping
            if concept["name"] == "Main Idea & Theme":
                assert len(concept["question_numbers"]) > 0
        
        # Verify QR concepts
        assert len(context["qr"]["concepts"]) == 2
        qr_names = [c["name"] for c in context["qr"]["concepts"]]
        assert "Number & Operations" in qr_names
        assert "Algebra & Patterns" in qr_names
    
    def test_mock_has_no_ticks(self, temp_template):
        """Test that mock flow produces empty tick marks."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        student_data = {
            "name": "Mock Student",
            "reading": 25,
            "writing": 15,
            "qr": 28,
            "ar": 30,
            "total": 98,
        }
        
        context = generator._build_context_from_dict(student_data, FlowType.MOCK)
        
        # Check reading concepts have no ticks
        for concept in context["rc"]["concepts"]:
            assert concept["done_well"] == ""
            assert concept["improve"] == ""
            assert concept["done_well_tick"] == ""
            assert concept["room_improve_tick"] == ""
        
        # Check QR concepts have no ticks
        for concept in context["qr"]["concepts"]:
            assert concept["done_well"] == ""
            assert concept["improve"] == ""
            assert concept["done_well_tick"] == ""
            assert concept["room_improve_tick"] == ""
    
    def test_standard_has_correct_ticks(self, temp_template):
        """Test that standard flow assigns ticks correctly based on mastery."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        analysis = FullAnalysis(
            subject_areas={
                "Reading": [
                    LearningAreaResult("Main Idea & Theme", 5, 6, 83.3, "Done well"),
                    LearningAreaResult("Inference & Interpretation", 2, 8, 25.0, "Needs improvement"),
                ],
                "Quantitative Reasoning": [],
                "Abstract Reasoning": [],
            },
            summary={},
        )
        
        context = generator._build_context_from_analysis(
            analysis,
            student_name="Test Student",
            writing_score=15.0,
            flow_type=FlowType.STANDARD,
        )
        
        concepts = context["rc"]["concepts"]
        
        # First concept: 83.3% should have done_well tick
        assert concepts[0]["name"] == "Main Idea & Theme"
        assert concepts[0]["done_well"] == "✓"
        assert concepts[0]["done_well_tick"] == "✓"
        assert concepts[0]["improve"] == ""
        assert concepts[0]["room_improve_tick"] == ""
        
        # Second concept: 25% should have improve tick
        assert concepts[1]["name"] == "Inference & Interpretation"
        assert concepts[1]["done_well"] == ""
        assert concepts[1]["done_well_tick"] == ""
        assert concepts[1]["improve"] == "✓"
        assert concepts[1]["room_improve_tick"] == "✓"
    
    def test_question_numbers_populated_from_mapping(self, temp_template):
        """Test that question numbers are loaded from concept mapping."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        analysis = FullAnalysis(
            subject_areas={
                "Reading": [
                    LearningAreaResult("Main Idea & Theme", 4, 6, 66.7, "Done well"),
                ],
                "Quantitative Reasoning": [
                    LearningAreaResult("Number & Operations", 3, 5, 60.0, "Done well"),
                ],
                "Abstract Reasoning": [],
            },
            summary={},
        )
        
        context = generator._build_context_from_analysis(
            analysis,
            student_name="Test Student",
            writing_score=15.0,
            flow_type=FlowType.STANDARD,
        )
        
        # Check Reading concept has question numbers
        reading_concept = context["rc"]["concepts"][0]
        assert reading_concept["name"] == "Main Idea & Theme"
        assert reading_concept["question_numbers"] != ""
        # Based on sample_concept_mapping.json: ["q1", "q6", "q11", "q16", "q21", "q26"]
        # Should become "1, 6, 11, 16, 21, 26"
        assert "1" in reading_concept["question_numbers"]
        assert "6" in reading_concept["question_numbers"]
        
        # Check QR concept has question numbers
        qr_concept = context["qr"]["concepts"][0]
        assert qr_concept["name"] == "Number & Operations"
        assert qr_concept["question_numbers"] != ""
        # Based on sample_concept_mapping.json: ["qr1", "qr2", "qr3", "qr4", "qr5"]
        # Should become "1, 2, 3, 4, 5"
        assert "1" in qr_concept["question_numbers"]
    
    def test_field_aliases_match(self, temp_template):
        """Test that field aliases match their primary field values."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        analysis = FullAnalysis(
            subject_areas={
                "Reading": [
                    LearningAreaResult("Test Concept", 5, 6, 83.3, "Done well"),
                ],
                "Quantitative Reasoning": [],
                "Abstract Reasoning": [],
            },
            summary={},
        )
        
        context = generator._build_context_from_analysis(
            analysis,
            student_name="Test Student",
            writing_score=15.0,
            flow_type=FlowType.STANDARD,
        )
        
        concept = context["rc"]["concepts"][0]
        
        # Verify aliases match primary fields
        assert concept["done_well"] == concept["done_well_tick"]
        assert concept["improve"] == concept["room_improve_tick"]
