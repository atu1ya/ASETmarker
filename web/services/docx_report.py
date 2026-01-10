"""
DocX Report Generation Service.

Production-grade Word document report generator using docxtpl (python-docx-template).
Supports three flows: Mock Generator, Single Student, and Batch Processing.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches, Mm

from web.services.analysis import FullAnalysis, LearningAreaResult

logger = logging.getLogger(__name__)


class FlowType(str, Enum):
    """Enum for report generation flow types."""
    MOCK = "mock"
    STANDARD = "standard"
    BATCH = "batch"


# Default concept mappings (used when no external mapping is provided)
DEFAULT_READING_CONCEPTS = [
    'Understanding main ideas',
    'Inference and deduction',
    'Identifying key details',
    'Vocabulary context clues',
    "Author's purpose and tone",
    'Cause and effect relationships',
    'Understanding tone and attitude',
    'Figurative / Literary devices',
]

DEFAULT_QR_CONCEPTS = [
    'Fractions / Decimals',
    'Time',
    'Algebra',
    'Geometry',
    'Graph / Data Interpretation',
    'Multiplication / Division',
    'Area / Perimeter',
    'Ratios / Unit Conversions',
    'Probability',
    'Patterns / Sequences',
    'Percentages',
]

# Mastery threshold (51%)
MASTERY_THRESHOLD = 51.0


@dataclass
class ConceptMastery:
    """Represents mastery status for a single concept."""
    name: str
    done_well: str
    improve: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for template context."""
        return {
            "name": self.name,
            "done_well": self.done_well,
            "improve": self.improve,
        }


@dataclass
class StudentReportData:
    """Structured data for a student report."""
    student_name: str
    reading_score: float
    writing_score: float
    qr_score: float
    ar_score: float
    total_score: float
    reading_concepts: List[ConceptMastery]
    qr_concepts: List[ConceptMastery]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], flow_type: FlowType = FlowType.STANDARD) -> "StudentReportData":
        """
        Create StudentReportData from a dictionary.
        
        Args:
            data: Dictionary containing student data
            flow_type: The type of flow (affects concept mastery calculation)
            
        Returns:
            StudentReportData instance
        """
        reading_concepts = []
        qr_concepts = []
        
        # Extract reading concepts
        reading_concept_data = data.get('reading_concepts', [])
        if isinstance(reading_concept_data, list):
            for concept in reading_concept_data:
                if isinstance(concept, dict):
                    reading_concepts.append(ConceptMastery(
                        name=concept.get('name', ''),
                        done_well=concept.get('done_well', ''),
                        improve=concept.get('improve', ''),
                    ))
                elif isinstance(concept, ConceptMastery):
                    reading_concepts.append(concept)
        
        # Extract QR concepts
        qr_concept_data = data.get('qr_concepts', [])
        if isinstance(qr_concept_data, list):
            for concept in qr_concept_data:
                if isinstance(concept, dict):
                    qr_concepts.append(ConceptMastery(
                        name=concept.get('name', ''),
                        done_well=concept.get('done_well', ''),
                        improve=concept.get('improve', ''),
                    ))
                elif isinstance(concept, ConceptMastery):
                    qr_concepts.append(concept)
        
        return cls(
            student_name=data.get('student_name', data.get('name', 'Unknown Student')),
            reading_score=float(data.get('reading_score', data.get('reading', 0))),
            writing_score=float(data.get('writing_score', data.get('writing', 0))),
            qr_score=float(data.get('qr_score', data.get('qr', 0))),
            ar_score=float(data.get('ar_score', data.get('ar', 0))),
            total_score=float(data.get('total_score', data.get('total', 0))),
            reading_concepts=reading_concepts,
            qr_concepts=qr_concepts,
        )


class DocxReportGenerator:
    """
    Production-grade Word document report generator.
    
    Generates branded student performance reports from a Word template
    using docxtpl for Jinja2-based template rendering.
    
    Supports three flows:
    - Mock: No concept mastery evaluation (all checkmarks blank)
    - Standard: Full mastery evaluation based on 51% threshold
    - Batch: Same as Standard, for multiple students
    
    Template Context Structure
    --------------------------
    The template receives a context dictionary with the following structure:
    
    ```
    {
        "student_name": "John Smith",
        "total_score": 85.00,
        "writing_score": 25.00,
        "graph_image": <InlineImage>,  # Bar chart as inline image
        
        "rc": {
            "score": 28.00,
            "total": 35.00,
            "percentage": 80.00,
            "concepts": [
                {"name": "Main Idea & Theme", "done_well": "✓", "improve": ""},
                {"name": "Inference & Interpretation", "done_well": "", "improve": "✓"},
                ...
            ]
        },
        
        "qr": {
            "score": 30.00,
            "total": 35.00,
            "percentage": 85.71,
            "concepts": [...]
        },
        
        "ar": {
            "score": 27.00,
            "total": 35.00,
            "percentage": 77.14
        },
        
        # Backward compatibility aliases
        "reading": {...},  # Same as 'rc'
        "reading_score": 28.00,
        "qr_score": 30.00,
        "ar_score": 27.00,
        "reading_concepts": [...],
        "qr_concepts": [...]
    }
    ```
    
    Template Syntax Examples
    ------------------------
    Use Jinja2 syntax within the Word template:
    
    - Simple values: {{ student_name }}, {{ total_score }}
    - Nested values: {{ rc.score }}, {{ rc.percentage }}, {{ qr.score }}
    - Inline image: {{ graph_image }}
    
    - Concept table loop:
        {% for c in rc.concepts %}
        {{ c.name }} | {{ c.done_well }} | {{ c.improve }}
        {% endfor %}
    
    - Conditional display:
        {% if rc.percentage >= 51 %}Passed{% else %}Needs work{% endif %}
    
    Notes:
    - Primary keys are 'rc' (Reading Comprehension), 'qr', and 'ar'
    - 'reading' is provided as an alias for backward compatibility
    - All numeric values are rounded to 2 decimal places
    - Checkmarks use Unicode "✓" character
    - Mock flow leaves all checkmark columns blank
    - Concept names come from the actual concept mapping JSON, not hardcoded defaults
    """
    
    def __init__(
        self,
        template_path: Optional[Path] = None,
        concept_mapping: Optional[Dict[str, Dict[str, List[str]]]] = None,
    ):
        """
        Initialize the DocxReportGenerator.
        
        Args:
            template_path: Path to the Word template file. 
                          Defaults to config/report_template.docx
            concept_mapping: Optional mapping of subjects to concepts and question IDs.
                           Used for calculating mastery in Standard/Batch flows.
        """
        if template_path is None:
            # Default to config/report_template.docx
            self.template_path = Path(__file__).parent.parent.parent / "config" / "report_template.docx"
        else:
            self.template_path = Path(template_path)
        
        self.concept_mapping = concept_mapping
        self._validate_template()
        
        logger.info(f"DocxReportGenerator initialized with template: {self.template_path}")
    
    def _validate_template(self) -> None:
        """Validate that the template file exists and is readable."""
        if not self.template_path.exists():
            raise FileNotFoundError(
                f"Report template not found at: {self.template_path}. "
                "Please ensure the template file exists."
            )
        
        if not self.template_path.suffix.lower() == '.docx':
            raise ValueError(
                f"Template must be a .docx file, got: {self.template_path.suffix}"
            )
    
    def _create_bar_chart(
        self,
        student_name: str,
        scores: Dict[str, float],
        max_scores: Optional[Dict[str, float]] = None,
    ) -> io.BytesIO:
        """
        Generate a bar chart comparing student scores to maximum scores.
        
        Args:
            student_name: Name of the student (for chart title)
            scores: Dictionary of subject names to student scores
            max_scores: Optional dictionary of subject names to max scores
            
        Returns:
            BytesIO buffer containing the chart as PNG image
        """
        fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
        
        subjects = list(scores.keys())
        student_values = [scores[s] for s in subjects]
        
        # Default max scores if not provided
        if max_scores is None:
            max_scores = {s: 100 for s in subjects}
        max_values = [max_scores.get(s, 100) for s in subjects]
        
        x = range(len(subjects))
        width = 0.35
        
        # Create bars
        bars1 = ax.bar([i - width/2 for i in x], student_values, width, 
                       label='Student Score', color='#3498DB', edgecolor='white')
        bars2 = ax.bar([i + width/2 for i in x], max_values, width,
                       label='Maximum Score', color='#95A5A6', edgecolor='white')
        
        # Customize chart
        ax.set_xlabel('Subject', fontweight='bold', fontsize=10)
        ax.set_ylabel('Score', fontweight='bold', fontsize=10)
        ax.set_title(f'Performance Summary', fontweight='bold', fontsize=12)
        ax.set_xticks(list(x))
        ax.set_xticklabels(subjects, fontsize=9)
        ax.legend(loc='upper right', fontsize=8)
        ax.set_ylim(0, max(max_values) * 1.1)
        
        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax.annotate(f'{height:.0f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=8)
        
        # Add gridlines
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)
        
        plt.tight_layout()
        
        # Save to buffer
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', bbox_inches='tight', facecolor='white')
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    def _build_concept_mastery_list(
        self,
        default_concept_names: List[str],
        area_results: Optional[List[LearningAreaResult]] = None,
        flow_type: FlowType = FlowType.STANDARD,
    ) -> List[Dict[str, str]]:
        """
        Build concept mastery list with tick marks.
        
        When area_results is provided (standard/batch flow with analysis), the
        concept names are extracted directly from the LearningAreaResult objects.
        When area_results is None (mock flow or no analysis), uses default_concept_names.
        
        Args:
            default_concept_names: Fallback list of concept names (used when no area_results)
            area_results: Optional list of LearningAreaResult objects with mastery data
            flow_type: The flow type (affects mastery calculation)
            
        Returns:
            List of dictionaries with name, done_well, and improve keys
        """
        concepts = []
        
        if flow_type == FlowType.MOCK:
            # Mock flow: use default concept names with empty checkmarks
            for concept_name in default_concept_names:
                concepts.append({
                    "name": concept_name,
                    "done_well": "",
                    "improve": "",
                })
        elif area_results:
            # Standard/Batch flow WITH analysis: use actual concept names from results
            for result in area_results:
                if result.status == "Done well" or result.percentage >= MASTERY_THRESHOLD:
                    concepts.append({
                        "name": result.area,
                        "done_well": "✓",
                        "improve": "",
                    })
                else:
                    concepts.append({
                        "name": result.area,
                        "done_well": "",
                        "improve": "✓",
                    })
        else:
            # Standard/Batch flow WITHOUT analysis: use defaults with "needs improvement"
            for concept_name in default_concept_names:
                concepts.append({
                    "name": concept_name,
                    "done_well": "",
                    "improve": "✓",
                })
        
        return concepts
    
    def _build_context_from_analysis(
        self,
        analysis: FullAnalysis,
        student_name: str,
        writing_score: float = 0,
        flow_type: FlowType = FlowType.STANDARD,
    ) -> Dict[str, Any]:
        """
        Build template context from a FullAnalysis object.
        
        Args:
            analysis: FullAnalysis object from the marking process
            student_name: Name of the student
            writing_score: Writing score (not in OMR analysis)
            flow_type: The flow type
            
        Returns:
            Dictionary ready to be passed to docxtpl with nested subject structures
        """
        # Extract area results from analysis
        # Map full subject names to short codes
        reading_areas = analysis.subject_areas.get('Reading', [])
        qr_areas = analysis.subject_areas.get('Quantitative Reasoning', [])
        ar_areas = analysis.subject_areas.get('Abstract Reasoning', [])
        
        # Calculate scores and totals from area results
        reading_correct = sum(a.correct for a in reading_areas)
        reading_total = sum(a.total for a in reading_areas)
        reading_percentage = (reading_correct / reading_total * 100) if reading_total > 0 else 0
        
        qr_correct = sum(a.correct for a in qr_areas)
        qr_total = sum(a.total for a in qr_areas)
        qr_percentage = (qr_correct / qr_total * 100) if qr_total > 0 else 0
        
        ar_correct = sum(a.correct for a in ar_areas)
        ar_total = sum(a.total for a in ar_areas)
        ar_percentage = (ar_correct / ar_total * 100) if ar_total > 0 else 0
        
        total_score = reading_correct + qr_correct + ar_correct + writing_score
        
        # Build concept lists with mastery ticks
        reading_concepts = self._build_concept_mastery_list(
            DEFAULT_READING_CONCEPTS, reading_areas, flow_type
        )
        qr_concepts = self._build_concept_mastery_list(
            DEFAULT_QR_CONCEPTS, qr_areas, flow_type
        )
        
        return {
            "student_name": student_name,
            "total_score": round(total_score, 2),
            "writing_score": round(writing_score, 2),
            # Reading Comprehension structure (key: 'rc')
            "rc": {
                "score": round(reading_correct, 2),
                "total": round(reading_total, 2),
                "percentage": round(reading_percentage, 2),
                "concepts": reading_concepts,
            },
            # Quantitative Reasoning structure (key: 'qr')
            "qr": {
                "score": round(qr_correct, 2),
                "total": round(qr_total, 2),
                "percentage": round(qr_percentage, 2),
                "concepts": qr_concepts,
            },
            # Abstract Reasoning structure (key: 'ar')
            "ar": {
                "score": round(ar_correct, 2),
                "total": round(ar_total, 2),
                "percentage": round(ar_percentage, 2),
            },
            # Backward compatibility aliases
            "reading": {
                "score": round(reading_correct, 2),
                "total": round(reading_total, 2),
                "percentage": round(reading_percentage, 2),
                "concepts": reading_concepts,
            },
            "reading_score": round(reading_correct, 2),
            "qr_score": round(qr_correct, 2),
            "ar_score": round(ar_correct, 2),
            "reading_concepts": reading_concepts,
            "qr_concepts": qr_concepts,
        }
    
    def _build_context_from_dict(
        self,
        student_data: Dict[str, Any],
        flow_type: FlowType = FlowType.STANDARD,
    ) -> Dict[str, Any]:
        """
        Build template context from a dictionary (e.g., from CSV parsing).
        
        Args:
            student_data: Dictionary with student data
            flow_type: The flow type
            
        Returns:
            Dictionary ready to be passed to docxtpl with nested subject structures
        """
        student_name = student_data.get('name', student_data.get('student_name', 'Unknown'))
        reading_score = float(student_data.get('reading', student_data.get('reading_score', 0)))
        writing_score = float(student_data.get('writing', student_data.get('writing_score', 0)))
        qr_score = float(student_data.get('qr', student_data.get('qr_score', 0)))
        ar_score = float(student_data.get('ar', student_data.get('ar_score', 0)))
        total_score = float(student_data.get('total', student_data.get('total_score', 0)))
        
        # Default totals for percentage calculation (standard test totals)
        reading_total = float(student_data.get('reading_total', 35))
        qr_total = float(student_data.get('qr_total', 35))
        ar_total = float(student_data.get('ar_total', 35))
        
        # Calculate percentages
        reading_percentage = (reading_score / reading_total * 100) if reading_total > 0 else 0
        qr_percentage = (qr_score / qr_total * 100) if qr_total > 0 else 0
        ar_percentage = (ar_score / ar_total * 100) if ar_total > 0 else 0
        
        # For mock flow, or if no analysis data is provided, use empty mastery
        reading_concepts = self._build_concept_mastery_list(
            DEFAULT_READING_CONCEPTS, None, flow_type
        )
        qr_concepts = self._build_concept_mastery_list(
            DEFAULT_QR_CONCEPTS, None, flow_type
        )
        
        return {
            "student_name": student_name,
            "total_score": round(total_score, 2),
            "writing_score": round(writing_score, 2),
            # Reading Comprehension structure (key: 'rc')
            "rc": {
                "score": round(reading_score, 2),
                "total": round(reading_total, 2),
                "percentage": round(reading_percentage, 2),
                "concepts": reading_concepts,
            },
            # Quantitative Reasoning structure (key: 'qr')
            "qr": {
                "score": round(qr_score, 2),
                "total": round(qr_total, 2),
                "percentage": round(qr_percentage, 2),
                "concepts": qr_concepts,
            },
            # Abstract Reasoning structure (key: 'ar')
            "ar": {
                "score": round(ar_score, 2),
                "total": round(ar_total, 2),
                "percentage": round(ar_percentage, 2),
            },
            # Backward compatibility aliases
            "reading": {
                "score": round(reading_score, 2),
                "total": round(reading_total, 2),
                "percentage": round(reading_percentage, 2),
                "concepts": reading_concepts,
            },
            "reading_score": round(reading_score, 2),
            "qr_score": round(qr_score, 2),
            "ar_score": round(ar_score, 2),
            "reading_concepts": reading_concepts,
            "qr_concepts": qr_concepts,
        }
    
    def generate_report(
        self,
        student_data: Dict[str, Any],
        flow_type: str = "standard",
        analysis: Optional[FullAnalysis] = None,
    ) -> io.BytesIO:
        """
        Generate a Word document report for a student.
        
        Args:
            student_data: Dictionary containing student information and scores.
                         Required keys: name/student_name
                         Score keys: reading, writing, qr, ar, total (or variants)
            flow_type: One of 'mock', 'standard', or 'batch'
            analysis: Optional FullAnalysis object for mastery calculation
            
        Returns:
            BytesIO buffer containing the generated .docx file
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If required data is missing
        """
        # Validate and normalize flow_type
        try:
            flow = FlowType(flow_type.lower())
        except ValueError:
            logger.warning(f"Unknown flow_type '{flow_type}', defaulting to 'standard'")
            flow = FlowType.STANDARD
        
        # Build context based on data source
        if analysis is not None:
            student_name = student_data.get('name', student_data.get('student_name', 'Unknown'))
            writing_score = float(student_data.get('writing', student_data.get('writing_score', 0)))
            context = self._build_context_from_analysis(
                analysis, student_name, writing_score, flow
            )
        else:
            context = self._build_context_from_dict(student_data, flow)
        
        # Load template
        doc = DocxTemplate(self.template_path)
        
        # Generate and add chart image
        scores = {
            "Reading": context["reading"]["score"],
            "Writing": context["writing_score"],
            "QR": context["qr"]["score"],
            "AR": context["ar"]["score"],
        }
        
        chart_buffer = self._create_bar_chart(
            context["student_name"],
            scores,
        )
        
        # Create InlineImage for the chart
        # Note: We need to pass the doc object to InlineImage
        graph_image = InlineImage(doc, chart_buffer, width=Inches(5))
        context["graph_image"] = graph_image
        
        # Render the template
        doc.render(context)
        
        # Save to buffer
        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        output_buffer.seek(0)
        
        logger.info(f"Generated report for {context['student_name']} (flow: {flow.value})")
        
        return output_buffer
    
    def generate_report_bytes(
        self,
        student_data: Dict[str, Any],
        flow_type: str = "standard",
        analysis: Optional[FullAnalysis] = None,
    ) -> bytes:
        """
        Generate a Word document report and return as bytes.
        
        Convenience wrapper around generate_report().
        
        Args:
            student_data: Dictionary containing student information
            flow_type: One of 'mock', 'standard', or 'batch'
            analysis: Optional FullAnalysis object
            
        Returns:
            Bytes of the generated .docx file
        """
        buffer = self.generate_report(student_data, flow_type, analysis)
        return buffer.getvalue()
