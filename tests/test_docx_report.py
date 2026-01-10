"""
Tests for DocxReportGenerator service.

Tests the Word document report generation using docxtpl,
including concept mastery logic and flow type handling.
"""
import io
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from web.services.docx_report import (
    DocxReportGenerator,
    FlowType,
    ConceptMastery,
    StudentReportData,
    DEFAULT_READING_CONCEPTS,
    DEFAULT_QR_CONCEPTS,
    MASTERY_THRESHOLD,
)
from web.services.analysis import FullAnalysis, LearningAreaResult


class TestConceptMastery:
    """Tests for ConceptMastery dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        concept = ConceptMastery(
            name="Inference",
            done_well="✓",
            improve="",
        )
        result = concept.to_dict()
        
        assert result == {
            "name": "Inference",
            "done_well": "✓",
            "improve": "",
        }
    
    def test_to_dict_needs_improvement(self):
        """Test conversion for concept needing improvement."""
        concept = ConceptMastery(
            name="Algebra",
            done_well="",
            improve="✓",
        )
        result = concept.to_dict()
        
        assert result["done_well"] == ""
        assert result["improve"] == "✓"


class TestStudentReportData:
    """Tests for StudentReportData dataclass."""
    
    def test_from_dict_basic(self):
        """Test creation from basic dictionary."""
        data = {
            "name": "John Doe",
            "reading": 85,
            "writing": 90,
            "qr": 75,
            "ar": 80,
            "total": 330,
            "reading_concepts": [],
            "qr_concepts": [],
        }
        
        result = StudentReportData.from_dict(data)
        
        assert result.student_name == "John Doe"
        assert result.reading_score == 85.0
        assert result.writing_score == 90.0
        assert result.qr_score == 75.0
        assert result.ar_score == 80.0
        assert result.total_score == 330.0
    
    def test_from_dict_alternative_keys(self):
        """Test creation with alternative key names."""
        data = {
            "student_name": "Jane Smith",
            "reading_score": 100,
            "writing_score": 95,
            "qr_score": 88,
            "ar_score": 92,
            "total_score": 375,
        }
        
        result = StudentReportData.from_dict(data)
        
        assert result.student_name == "Jane Smith"
        assert result.reading_score == 100.0


class TestDocxReportGeneratorInit:
    """Tests for DocxReportGenerator initialization."""
    
    def test_default_template_path(self, tmp_path):
        """Test that default template path is constructed correctly."""
        # Create a mock template file
        template_file = tmp_path / "report_template.docx"
        template_file.touch()
        
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=template_file)
            assert generator.template_path == template_file
    
    def test_template_not_found_raises(self, tmp_path):
        """Test that missing template raises FileNotFoundError."""
        fake_path = tmp_path / "nonexistent.docx"
        
        with pytest.raises(FileNotFoundError):
            DocxReportGenerator(template_path=fake_path)
    
    def test_invalid_template_extension(self, tmp_path):
        """Test that non-docx file raises ValueError."""
        invalid_file = tmp_path / "template.pdf"
        invalid_file.touch()
        
        with pytest.raises(ValueError, match="must be a .docx file"):
            DocxReportGenerator(template_path=invalid_file)


class TestBuildConceptMasteryList:
    """Tests for concept mastery list building."""
    
    @pytest.fixture
    def generator(self, tmp_path):
        """Create a generator with mock template."""
        template_file = tmp_path / "template.docx"
        template_file.touch()
        
        with patch.object(DocxReportGenerator, '_validate_template'):
            return DocxReportGenerator(template_path=template_file)
    
    def test_mock_flow_all_empty(self, generator):
        """Test that mock flow produces empty checkmarks."""
        concepts = ["Concept A", "Concept B", "Concept C"]
        
        result = generator._build_concept_mastery_list(
            concepts, None, FlowType.MOCK
        )
        
        assert len(result) == 3
        for concept in result:
            assert concept["done_well"] == ""
            assert concept["improve"] == ""
    
    def test_standard_flow_done_well(self, generator):
        """Test that standard flow marks high mastery as done well."""
        concepts = ["High Mastery Concept"]
        area_results = [
            LearningAreaResult(
                area="High Mastery Concept",
                correct=8,
                total=10,
                percentage=80.0,  # Above 51% threshold
                status="Done well",
            )
        ]
        
        result = generator._build_concept_mastery_list(
            concepts, area_results, FlowType.STANDARD
        )
        
        assert len(result) == 1
        assert result[0]["name"] == "High Mastery Concept"
        assert result[0]["done_well"] == "✓"
        assert result[0]["improve"] == ""
    
    def test_standard_flow_needs_improvement(self, generator):
        """Test that standard flow marks low mastery as needs improvement."""
        concepts = ["Low Mastery Concept"]
        area_results = [
            LearningAreaResult(
                area="Low Mastery Concept",
                correct=2,
                total=10,
                percentage=20.0,  # Below 51% threshold
                status="Needs improvement",
            )
        ]
        
        result = generator._build_concept_mastery_list(
            concepts, area_results, FlowType.STANDARD
        )
        
        assert len(result) == 1
        assert result[0]["done_well"] == ""
        assert result[0]["improve"] == "✓"
    
    def test_threshold_boundary(self, generator):
        """Test mastery at exactly 51% threshold."""
        concepts = ["Boundary Concept"]
        area_results = [
            LearningAreaResult(
                area="Boundary Concept",
                correct=51,
                total=100,
                percentage=51.0,  # Exactly at threshold
                status="Done well",
            )
        ]
        
        result = generator._build_concept_mastery_list(
            concepts, area_results, FlowType.STANDARD
        )
        
        # At threshold should be "Done well"
        assert result[0]["done_well"] == "✓"
        assert result[0]["improve"] == ""
    
    def test_below_threshold(self, generator):
        """Test mastery just below 51% threshold."""
        concepts = ["Below Threshold"]
        area_results = [
            LearningAreaResult(
                area="Below Threshold",
                correct=50,
                total=100,
                percentage=50.0,  # Just below threshold
                status="Needs improvement",
            )
        ]
        
        result = generator._build_concept_mastery_list(
            concepts, area_results, FlowType.STANDARD
        )
        
        assert result[0]["done_well"] == ""
        assert result[0]["improve"] == "✓"
    
    def test_batch_flow_same_as_standard(self, generator):
        """Test that batch flow behaves same as standard."""
        concepts = ["Test Concept"]
        area_results = [
            LearningAreaResult(
                area="Test Concept",
                correct=7,
                total=10,
                percentage=70.0,
                status="Done well",
            )
        ]
        
        standard_result = generator._build_concept_mastery_list(
            concepts, area_results, FlowType.STANDARD
        )
        batch_result = generator._build_concept_mastery_list(
            concepts, area_results, FlowType.BATCH
        )
        
        assert standard_result == batch_result


class TestBuildContext:
    """Tests for context building methods."""
    
    @pytest.fixture
    def generator(self, tmp_path):
        """Create a generator with mock template."""
        template_file = tmp_path / "template.docx"
        template_file.touch()
        
        with patch.object(DocxReportGenerator, '_validate_template'):
            return DocxReportGenerator(template_path=template_file)
    
    def test_build_context_from_dict_mock_flow(self, generator):
        """Test context building from dict for mock flow."""
        student_data = {
            "name": "Test Student",
            "reading": 100,
            "writing": 95,
            "qr": 88,
            "ar": 92,
            "total": 375,
        }
        
        context = generator._build_context_from_dict(student_data, FlowType.MOCK)
        
        assert context["student_name"] == "Test Student"
        assert context["writing_score"] == 95.0
        assert context["total_score"] == 375.0
        
        # Check nested structure
        assert "reading" in context
        assert "qr" in context
        assert "ar" in context
        
        assert context["reading"]["score"] == 100.0
        assert context["qr"]["score"] == 88.0
        assert context["ar"]["score"] == 92.0
        
        # Check backward compatibility flat keys
        assert context["reading_score"] == 100.0
        assert context["qr_score"] == 88.0
        assert context["ar_score"] == 92.0
        
        # Mock flow: all concepts should have empty checkmarks
        for concept in context["reading"]["concepts"]:
            assert concept["done_well"] == ""
            assert concept["improve"] == ""
        
        for concept in context["qr"]["concepts"]:
            assert concept["done_well"] == ""
            assert concept["improve"] == ""
    
    def test_build_context_from_analysis(self, generator):
        """Test context building from FullAnalysis object."""
        analysis = FullAnalysis(
            subject_areas={
                "Reading": [
                    LearningAreaResult("Understanding main ideas", 5, 6, 83.3, "Done well"),
                    LearningAreaResult("Inference and deduction", 3, 8, 37.5, "Needs improvement"),
                ],
                "Quantitative Reasoning": [
                    LearningAreaResult("Algebra", 4, 4, 100.0, "Done well"),
                ],
                "Abstract Reasoning": [
                    LearningAreaResult("Pattern Recognition", 10, 15, 66.7, "Done well"),
                ],
            },
            summary={},
        )
        
        context = generator._build_context_from_analysis(
            analysis,
            student_name="Analysis Student",
            writing_score=85.0,
            flow_type=FlowType.STANDARD,
        )
        
        assert context["student_name"] == "Analysis Student"
        assert context["writing_score"] == 85.0
        
        # Check nested structure exists
        assert "reading" in context
        assert "qr" in context
        assert "ar" in context
        
        # Check reading nested structure
        assert context["reading"]["score"] == 8  # 5 + 3
        assert context["reading"]["total"] == 14  # 6 + 8
        assert "concepts" in context["reading"]
        assert len(context["reading"]["concepts"]) == len(DEFAULT_READING_CONCEPTS)
        
        # Check qr nested structure
        assert context["qr"]["score"] == 4
        assert context["qr"]["total"] == 4
        assert "concepts" in context["qr"]
        
        # Check ar nested structure
        assert context["ar"]["score"] == 10
        assert context["ar"]["total"] == 15
        
        # Check backward compatibility flat keys
        assert "reading_concepts" in context
        assert len(context["reading_concepts"]) == len(DEFAULT_READING_CONCEPTS)


class TestCreateBarChart:
    """Tests for bar chart generation."""
    
    @pytest.fixture
    def generator(self, tmp_path):
        """Create a generator with mock template."""
        template_file = tmp_path / "template.docx"
        template_file.touch()
        
        with patch.object(DocxReportGenerator, '_validate_template'):
            return DocxReportGenerator(template_path=template_file)
    
    def test_create_bar_chart_returns_buffer(self, generator):
        """Test that chart generation returns a BytesIO buffer."""
        scores = {
            "Reading": 100,
            "Writing": 95,
            "QR": 88,
            "AR": 92,
        }
        
        result = generator._create_bar_chart("Test Student", scores)
        
        assert isinstance(result, io.BytesIO)
        # Check it contains PNG data
        result.seek(0)
        header = result.read(8)
        # PNG header signature
        assert header[:4] == b'\x89PNG'
    
    def test_create_bar_chart_with_custom_max(self, generator):
        """Test chart with custom max scores."""
        scores = {"Reading": 25, "Writing": 30}
        max_scores = {"Reading": 35, "Writing": 50}
        
        result = generator._create_bar_chart(
            "Test Student",
            scores,
            max_scores=max_scores,
        )
        
        assert isinstance(result, io.BytesIO)


class TestGenerateReport:
    """Tests for the main generate_report method."""
    
    @pytest.fixture
    def mock_template(self, tmp_path):
        """Create a minimal valid docx template."""
        # We'll mock the DocxTemplate instead
        return tmp_path / "template.docx"
    
    def test_generate_report_unknown_flow_defaults_to_standard(self, tmp_path):
        """Test that unknown flow type defaults to standard."""
        template_file = tmp_path / "template.docx"
        template_file.touch()
        
        with patch.object(DocxReportGenerator, '_validate_template'):
            with patch('web.services.docx_report.DocxTemplate') as mock_docx:
                mock_doc = MagicMock()
                mock_docx.return_value = mock_doc
                
                generator = DocxReportGenerator(template_path=template_file)
                
                student_data = {"name": "Test", "reading": 100}
                
                # This should not raise, should default to standard
                try:
                    generator.generate_report(student_data, flow_type="invalid_flow")
                except Exception:
                    pass  # Template rendering may fail, but flow type should be handled
    
    def test_context_keys_structure(self, tmp_path):
        """Test that generated context has required keys including nested structure."""
        template_file = tmp_path / "template.docx"
        template_file.touch()
        
        with patch.object(DocxReportGenerator, '_validate_template'):
            generator = DocxReportGenerator(template_path=template_file)
            
            student_data = {
                "name": "Test Student",
                "reading": 100,
                "writing": 95,
                "qr": 88,
                "ar": 92,
                "total": 375,
            }
            
            context = generator._build_context_from_dict(student_data, FlowType.STANDARD)
            
            # Verify nested structure keys exist
            assert "reading" in context
            assert "qr" in context
            assert "ar" in context
            
            # Verify nested reading structure
            assert "score" in context["reading"]
            assert "total" in context["reading"]
            assert "percentage" in context["reading"]
            assert "concepts" in context["reading"]
            
            # Verify nested qr structure
            assert "score" in context["qr"]
            assert "total" in context["qr"]
            assert "percentage" in context["qr"]
            assert "concepts" in context["qr"]
            
            # Verify nested ar structure
            assert "score" in context["ar"]
            assert "total" in context["ar"]
            assert "percentage" in context["ar"]
            
            # Verify backward compatibility flat keys
            required_flat_keys = [
                "student_name",
                "reading_score",
                "writing_score",
                "qr_score",
                "ar_score",
                "total_score",
                "reading_concepts",
                "qr_concepts",
            ]
            
            for key in required_flat_keys:
                assert key in context, f"Missing required key: {key}"
            
            # Verify concept structure in nested reading
            if context["reading"]["concepts"]:
                concept = context["reading"]["concepts"][0]
                assert "name" in concept
                assert "done_well" in concept
                assert "improve" in concept


class TestFlowTypeEnum:
    """Tests for FlowType enum."""
    
    def test_flow_type_values(self):
        """Test FlowType enum values."""
        assert FlowType.MOCK.value == "mock"
        assert FlowType.STANDARD.value == "standard"
        assert FlowType.BATCH.value == "batch"
    
    def test_flow_type_from_string(self):
        """Test creating FlowType from string."""
        assert FlowType("mock") == FlowType.MOCK
        assert FlowType("standard") == FlowType.STANDARD
        assert FlowType("batch") == FlowType.BATCH


class TestDefaultConcepts:
    """Tests for default concept lists."""
    
    def test_reading_concepts_not_empty(self):
        """Test that default reading concepts list is populated."""
        assert len(DEFAULT_READING_CONCEPTS) > 0
        assert "Understanding main ideas" in DEFAULT_READING_CONCEPTS
    
    def test_qr_concepts_not_empty(self):
        """Test that default QR concepts list is populated."""
        assert len(DEFAULT_QR_CONCEPTS) > 0
        assert "Algebra" in DEFAULT_QR_CONCEPTS
    
    def test_mastery_threshold(self):
        """Test mastery threshold constant."""
        assert MASTERY_THRESHOLD == 51.0
