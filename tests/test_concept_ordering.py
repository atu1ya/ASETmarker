"""
Test concept ordering and question number population.

Verifies that concepts are always returned in default order with proper question numbers.
"""
from pathlib import Path
from unittest.mock import patch
import pytest

from web.services.docx_report import (
    DocxReportGenerator,
    FlowType,
    DEFAULT_READING_CONCEPTS,
    DEFAULT_QR_CONCEPTS,
    ConceptMastery,
)
from web.services.analysis import FullAnalysis, LearningAreaResult


class TestConceptOrdering:
    """Tests for concept ordering and question number mapping."""
    
    @pytest.fixture
    def temp_template(self, tmp_path):
        """Create a minimal valid Word template for testing."""
        template_file = tmp_path / "test_template.docx"
        template_file.touch()
        return template_file
    
    def test_concepts_always_in_default_order_mock(self, temp_template):
        """Test that mock flow returns concepts in default order."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        # Build concept list for mock flow (no area_results)
        concepts = generator._build_concept_mastery_list(
            DEFAULT_READING_CONCEPTS,
            'Reading',
            None,
            FlowType.MOCK
        )
        
        # Verify order matches default
        assert len(concepts) == len(DEFAULT_READING_CONCEPTS)
        for i, concept in enumerate(concepts):
            assert concept.name == DEFAULT_READING_CONCEPTS[i]
            assert concept.done_well == ""
            assert concept.improve == ""
            # Questions field should be populated from mapping
            assert isinstance(concept.questions, str)
    
    def test_concepts_always_in_default_order_with_results(self, temp_template):
        """Test that concepts maintain default order even when results are provided."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        # Create area_results in different order than default
        area_results = [
            LearningAreaResult("Vocabulary context clues", 4, 6, 66.7, "Done well"),
            LearningAreaResult("Understanding main ideas", 2, 6, 33.3, "Needs improvement"),
            LearningAreaResult("Inference and deduction", 5, 8, 62.5, "Done well"),
        ]
        
        concepts = generator._build_concept_mastery_list(
            DEFAULT_READING_CONCEPTS,
            'Reading',
            area_results,
            FlowType.STANDARD
        )
        
        # Verify order matches default, not the order of area_results
        assert len(concepts) == len(DEFAULT_READING_CONCEPTS)
        assert concepts[0].name == DEFAULT_READING_CONCEPTS[0]  # "Understanding main ideas"
        assert concepts[1].name == DEFAULT_READING_CONCEPTS[1]  # "Inference and deduction"
        assert concepts[3].name == DEFAULT_READING_CONCEPTS[3]  # "Vocabulary context clues"
        
        # Verify mastery ticks are correctly assigned
        # "Understanding main ideas" - 33.3% should have improve tick
        assert concepts[0].done_well == ""
        assert concepts[0].improve == "✓"
        
        # "Inference and deduction" - 62.5% should have done_well tick
        assert concepts[1].done_well == "✓"
        assert concepts[1].improve == ""
        
        # "Vocabulary context clues" - 66.7% should have done_well tick
        assert concepts[3].done_well == "✓"
        assert concepts[3].improve == ""
    
    def test_concepts_with_missing_results(self, temp_template):
        """Test that concepts without matching results get default improve tick."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        # Provide results for only 2 concepts
        area_results = [
            LearningAreaResult("Understanding main ideas", 5, 6, 83.3, "Done well"),
            LearningAreaResult("Inference and deduction", 3, 8, 37.5, "Needs improvement"),
        ]
        
        concepts = generator._build_concept_mastery_list(
            DEFAULT_READING_CONCEPTS,
            'Reading',
            area_results,
            FlowType.STANDARD
        )
        
        # All 8 default concepts should be present
        assert len(concepts) == 8
        
        # First two have matching results
        assert concepts[0].name == "Understanding main ideas"
        assert concepts[0].done_well == "✓"
        assert concepts[0].improve == ""
        
        assert concepts[1].name == "Inference and deduction"
        assert concepts[1].done_well == ""
        assert concepts[1].improve == "✓"
        
        # Remaining concepts should have default improve tick
        for i in range(2, 8):
            assert concepts[i].name == DEFAULT_READING_CONCEPTS[i]
            assert concepts[i].done_well == ""
            assert concepts[i].improve == "✓"
    
    def test_question_numbers_populated(self, temp_template):
        """Test that question numbers are populated from concept mapping."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        concepts = generator._build_concept_mastery_list(
            DEFAULT_READING_CONCEPTS,
            'Reading',
            None,
            FlowType.MOCK
        )
        
        # Check that questions field is populated (not empty for concepts in mapping)
        # Note: Some concepts may not be in the mapping file, so we check for at least one
        has_questions = any(c.questions != "" for c in concepts)
        assert has_questions, "At least one concept should have question numbers from mapping"
    
    def test_qr_concepts_in_order(self, temp_template):
        """Test that QR concepts also maintain default order."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        # Create results in different order
        area_results = [
            LearningAreaResult("Geometry", 4, 5, 80.0, "Done well"),
            LearningAreaResult("Fractions / Decimals", 3, 5, 60.0, "Done well"),
        ]
        
        concepts = generator._build_concept_mastery_list(
            DEFAULT_QR_CONCEPTS,
            'Quantitative Reasoning',
            area_results,
            FlowType.STANDARD
        )
        
        # Verify order matches default
        assert len(concepts) == len(DEFAULT_QR_CONCEPTS)
        assert concepts[0].name == DEFAULT_QR_CONCEPTS[0]  # "Fractions / Decimals"
        assert concepts[3].name == DEFAULT_QR_CONCEPTS[3]  # "Geometry"
        
        # Verify ticks
        assert concepts[0].done_well == "✓"  # Has matching result with 60%
        assert concepts[3].done_well == "✓"  # Has matching result with 80%
    
    def test_concept_mastery_dataclass_has_questions(self):
        """Test that ConceptMastery dataclass includes questions field."""
        concept = ConceptMastery(
            name="Test Concept",
            done_well="✓",
            improve="",
            questions="1, 6, 11"
        )
        
        assert concept.name == "Test Concept"
        assert concept.done_well == "✓"
        assert concept.improve == ""
        assert concept.questions == "1, 6, 11"
        
        # Test to_dict includes questions
        concept_dict = concept.to_dict()
        assert "questions" in concept_dict
        assert concept_dict["questions"] == "1, 6, 11"
    
    def test_full_context_has_question_numbers_alias(self, temp_template):
        """Test that full context includes both questions and question_numbers fields."""
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=temp_template)
        
        analysis = FullAnalysis(
            subject_areas={
                "Reading": [
                    LearningAreaResult("Understanding main ideas", 5, 6, 83.3, "Done well"),
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
        
        # Check that concepts have both questions and question_numbers
        concept = context["rc"]["concepts"][0]
        assert "questions" in concept
        assert "question_numbers" in concept
        # They should be aliases (same value)
        assert concept["questions"] == concept["question_numbers"]
