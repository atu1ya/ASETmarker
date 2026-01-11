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


def _load_concept_question_mapping() -> Dict[str, Dict[str, str]]:
    """Load concept to question numbers mapping from config file.
    
    Returns:
        Dict with structure: {'Reading': {'concept_name': 'q1, q2, q3'}, 'Quantitative Reasoning': {...}}
    """
    import json
    
    # Try to load from sample_concept_mapping.json
    config_path = Path(__file__).parent.parent.parent / "docs" / "sample_concept_mapping.json"
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                raw_mapping = json.load(f)
            
            # Convert list of question IDs to comma-separated string
            result = {}
            for subject in ['Reading', 'Quantitative Reasoning']:
                if subject in raw_mapping:
                    result[subject] = {}
                    for concept_name, question_list in raw_mapping[subject].items():
                        # Remove 'q' or 'qr' prefix and join with commas
                        clean_nums = [q.replace('q', '').replace('r', '') for q in question_list]
                        result[subject][concept_name] = ', '.join(clean_nums)
            
            return result
    except Exception as e:
        logger.warning(f"Could not load concept mapping: {e}")
    
    # Fallback: empty mapping
    return {'Reading': {}, 'Quantitative Reasoning': {}}


# Load question number mapping at module level
CONCEPT_QUESTION_MAPPING = _load_concept_question_mapping()


@dataclass
class ConceptMastery:
    """Represents mastery status for a single concept."""
    name: str
    done_well: str
    improve: str
    questions: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for template context."""
        return {
            "name": self.name,
            "done_well": self.done_well,
            "improve": self.improve,
            "questions": self.questions,
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
            student_name=str(data.get('student_name', data.get('name', 'Unknown Student'))).title(),
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
    ) -> io.BytesIO:
        """
        Generate a bar chart showing student scores only.
        
        Args:
            student_name: Name of the student (for chart title)
            scores: Dictionary of subject names to student scores
            
        Returns:
            BytesIO buffer containing the chart as PNG image
        """
        fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
        
        subjects = list(scores.keys())
        student_values = [scores[s] for s in subjects]
        
        x = range(len(subjects))
        
        # Create single bar for student scores
        bars = ax.bar(x, student_values, color='#3498DB', edgecolor='white', width=0.6)
        
        # Customize chart
        ax.set_xlabel('Subject', fontweight='bold', fontsize=10)
        ax.set_ylabel('Score', fontweight='bold', fontsize=10)
        ax.set_title(f'Performance Summary', fontweight='bold', fontsize=12)
        ax.set_xticks(list(x))
        ax.set_xticklabels(subjects, fontsize=9)
        
        # Set y-axis limit with some padding
        max_value = max(student_values) if student_values else 100
        ax.set_ylim(0, max_value * 1.15)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.0f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)
        
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
        concept_names: List[str],
        subject_name: str,
        area_results: Optional[List[LearningAreaResult]] = None,
        flow_type: FlowType = FlowType.STANDARD,
    ) -> List[ConceptMastery]:
        """
        Build concept mastery list with tick marks and question numbers.
        
        Uses actual concept names from area_results when available.
        For each concept, prioritizes question_numbers from LearningAreaResult,
        falling back to CONCEPT_QUESTION_MAPPING if needed.
        
        Args:
            concept_names: List of concept names (used as fallback if no area_results)
            subject_name: Subject name for question number lookup (e.g., 'Reading', 'Quantitative Reasoning')
            area_results: Optional list of LearningAreaResult objects with mastery data
            flow_type: The flow type (affects mastery calculation)
            
        Returns:
            List of ConceptMastery objects
        """
        concepts = []
        question_map = CONCEPT_QUESTION_MAPPING.get(subject_name, {})
        
        if flow_type == FlowType.MOCK:
            # Mock flow: use provided concept names with empty checkmarks
            for concept_name in concept_names:
                questions = question_map.get(concept_name, '')
                concepts.append(ConceptMastery(
                    name=concept_name,
                    done_well="",
                    improve="",
                    questions=questions,
                ))
        elif area_results:
            # Standard/Batch flow WITH analysis: use actual results from analysis
            for result in area_results:
                # Prioritize question_numbers from result, fallback to mapping
                if hasattr(result, 'question_numbers') and result.question_numbers:
                    questions = result.question_numbers
                else:
                    questions = question_map.get(result.area, '')
                
                # Verify percentage >= MASTERY_THRESHOLD (51.0) for "Done well"
                if result.percentage >= MASTERY_THRESHOLD:
                    done_well = "✓"
                    improve = ""
                else:
                    done_well = ""
                    improve = "✓"
                
                concepts.append(ConceptMastery(
                    name=result.area,
                    done_well=done_well,
                    improve=improve,
                    questions=questions,
                ))
        else:
            # Standard/Batch flow WITHOUT analysis: use provided names with "needs improvement"
            for concept_name in concept_names:
                questions = question_map.get(concept_name, '')
                concepts.append(ConceptMastery(
                    name=concept_name,
                    done_well="",
                    improve="✓",
                    questions=questions,
                ))
        
        return concepts
    
    def _build_context_from_analysis(
        self,
        analysis: FullAnalysis,
        student_data: Dict[str, Any],
        flow_type: FlowType = FlowType.STANDARD,
    ) -> Dict[str, Any]:
        """
        Build template context from a FullAnalysis object.
        
        Args:
            analysis: FullAnalysis object from the marking process
            student_data: Dictionary containing student info and scores (name, writing_score, reading_score, qr_score, ar_score)
            flow_type: The flow type
            
        Returns:
            Dictionary ready to be passed to docxtpl with nested subject structures
        """
        # Extract student info
        student_name = str(student_data.get('name', student_data.get('student_name', 'Unknown'))).title()
        writing_score = float(student_data.get('writing', student_data.get('writing_score', 0)))
        # Extract area results from analysis
        # Map full subject names to short codes
        reading_areas = analysis.subject_areas.get('Reading', [])
        qr_areas = analysis.subject_areas.get('Quantitative Reasoning', [])
        ar_areas = analysis.subject_areas.get('Abstract Reasoning', [])
        
        # Use passed scores if available, otherwise calculate from area results
        if 'reading_score' in student_data:
            reading_correct = float(student_data['reading_score'])
        else:
            reading_correct = sum(a.correct for a in reading_areas)
        
        if 'qr_score' in student_data:
            qr_correct = float(student_data['qr_score'])
        else:
            qr_correct = sum(a.correct for a in qr_areas)
        
        if 'ar_score' in student_data:
            ar_correct = float(student_data['ar_score'])
        else:
            ar_correct = sum(a.correct for a in ar_areas)
        
        # Use passed totals if available, otherwise default to 35 (standard exam total)
        # This ensures correct percentages even if concept mapping is incomplete
        # HARDCODE: Always use 35 as the total for percentage calculations
        reading_total = 35.0
        qr_total = 35.0
        ar_total = 35.0
        
        # Calculate percentages based on fixed total of 35, rounded to 2 decimal places
        reading_percentage = round((reading_correct / reading_total * 100) if reading_total > 0 else 0, 2)
        qr_percentage = round((qr_correct / qr_total * 100) if qr_total > 0 else 0, 2)
        ar_percentage = round((ar_correct / ar_total * 100) if ar_total > 0 else 0, 2)
        
        # Writing score is already a percentage - use it directly
        writing_percentage = round(writing_score, 2)
        
        # Total score is sum of all 4 percentages
        total_score = reading_percentage + writing_percentage + qr_percentage + ar_percentage
        
        # Build concept lists with mastery ticks and question numbers
        # Use actual concept names from analysis results, not hardcoded defaults
        reading_concept_names = [area.area for area in reading_areas] if reading_areas else DEFAULT_READING_CONCEPTS
        qr_concept_names = [area.area for area in qr_areas] if qr_areas else DEFAULT_QR_CONCEPTS
        
        reading_concepts_objs = self._build_concept_mastery_list(
            reading_concept_names, 'Reading', reading_areas, flow_type
        )
        qr_concepts_objs = self._build_concept_mastery_list(
            qr_concept_names, 'Quantitative Reasoning', qr_areas, flow_type
        )
        
        # Convert to dicts with all fields including aliases
        reading_concepts = [
            {
                "name": c.name,
                "questions": c.questions,
                "question_numbers": c.questions,  # Alias
                "done_well": c.done_well,
                "improve": c.improve,
                "done_well_tick": c.done_well,  # Alias
                "room_improve_tick": c.improve,  # Alias
            }
            for c in reading_concepts_objs
        ]
        qr_concepts = [
            {
                "name": c.name,
                "questions": c.questions,
                "question_numbers": c.questions,  # Alias
                "done_well": c.done_well,
                "improve": c.improve,
                "done_well_tick": c.done_well,  # Alias
                "room_improve_tick": c.improve,  # Alias
            }
            for c in qr_concepts_objs
        ]
        
        return {
            "student_name": student_name,
            "total_score": round(total_score, 2),
            "writing_score": round(writing_score, 2),
            "writing_percentage": round(writing_percentage, 2),
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
            # TOP-LEVEL SCORES AS PERCENTAGES (for Jinja template)
            "reading_score": round(reading_percentage, 2),
            "qr_score": round(qr_percentage, 2),
            "ar_score": round(ar_percentage, 2),
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
        student_name = str(student_data.get('name', student_data.get('student_name', 'Unknown'))).title()
        reading_score = float(student_data.get('reading', student_data.get('reading_score', 0)))
        writing_score = float(student_data.get('writing', student_data.get('writing_score', 0)))
        qr_score = float(student_data.get('qr', student_data.get('qr_score', 0)))
        ar_score = float(student_data.get('ar', student_data.get('ar_score', 0)))
        total_score = float(student_data.get('total', student_data.get('total_score', 0)))
        
        if flow_type == FlowType.MOCK:
            # MOCK FLOW: Use standardised scores directly from CSV without any conversion
            # CSV columns: Standardised Reading Score, Standardised Writing Score, 
            # Standardised QR Score, Standardised AR Score, Total Standard Score (/400)
            reading_percentage = round(reading_score, 2)
            writing_percentage = round(writing_score, 2)
            qr_percentage = round(qr_score, 2)
            ar_percentage = round(ar_score, 2)
            # Use total directly from CSV (Total Standard Score (/400))
            total_score = round(total_score, 2)
            
            # For display in nested structures, use the scores as-is
            reading_total = 100.0  # Standardised scores are out of 100
            qr_total = 100.0
            ar_total = 100.0
        else:
            # STANDARD/BATCH FLOW: Calculate percentages from raw scores
            # HARDCODE: Always use 35 as the total for Reading/QR/AR
            reading_total = 35.0
            qr_total = 35.0
            ar_total = 35.0
            
            # Calculate percentages based on fixed totals, rounded to 2 decimal places
            reading_percentage = round((reading_score / reading_total * 100) if reading_total > 0 else 0, 2)
            qr_percentage = round((qr_score / qr_total * 100) if qr_total > 0 else 0, 2)
            ar_percentage = round((ar_score / ar_total * 100) if ar_total > 0 else 0, 2)
            
            # Writing score is already a percentage - use it directly
            writing_percentage = round(writing_score, 2)
            
            # Recalculate total_score as sum of all 4 percentages
            total_score = reading_percentage + writing_percentage + qr_percentage + ar_percentage
        
        # Check if concept data is provided in student_data
        # If provided, use it directly; otherwise fall back to defaults
        if 'reading_concepts' in student_data and isinstance(student_data['reading_concepts'], list):
            reading_concepts = student_data['reading_concepts']
        else:
            # For mock flow, or if no analysis data is provided, use empty mastery
            reading_concepts_objs = self._build_concept_mastery_list(
                DEFAULT_READING_CONCEPTS, 'Reading', None, flow_type
            )
            reading_concepts = [
                {
                    "name": c.name,
                    "questions": c.questions,
                    "question_numbers": c.questions,  # Alias
                    "done_well": c.done_well,
                    "improve": c.improve,
                    "done_well_tick": c.done_well,  # Alias
                    "room_improve_tick": c.improve,  # Alias
                }
                for c in reading_concepts_objs
            ]
        
        if 'qr_concepts' in student_data and isinstance(student_data['qr_concepts'], list):
            qr_concepts = student_data['qr_concepts']
        else:
            qr_concepts_objs = self._build_concept_mastery_list(
                DEFAULT_QR_CONCEPTS, 'Quantitative Reasoning', None, flow_type
            )
            qr_concepts = [
                {
                    "name": c.name,
                    "questions": c.questions,
                    "question_numbers": c.questions,  # Alias
                    "done_well": c.done_well,
                    "improve": c.improve,
                    "done_well_tick": c.done_well,  # Alias
                    "room_improve_tick": c.improve,  # Alias
                }
                for c in qr_concepts_objs
            ]
        
        return {
            "student_name": student_name,
            "total_score": round(total_score, 2),
            "writing_score": round(writing_score, 2),
            "writing_percentage": round(writing_percentage, 2),
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
            # TOP-LEVEL SCORES AS PERCENTAGES (for Jinja template)
            "reading_score": round(reading_percentage, 2),
            "qr_score": round(qr_percentage, 2),
            "ar_score": round(ar_percentage, 2),
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
            context = self._build_context_from_analysis(
                analysis, student_data, flow
            )
        else:
            context = self._build_context_from_dict(student_data, flow)
        
        # Ensure all required keys exist (prevent UndefinedError)
        if 'rc' not in context:
            context['rc'] = {'score': 0.0, 'total': 0.0, 'percentage': 0.0, 'concepts': []}
        if 'qr' not in context:
            context['qr'] = {'score': 0.0, 'total': 0.0, 'percentage': 0.0, 'concepts': []}
        if 'ar' not in context:
            context['ar'] = {'score': 0.0, 'total': 0.0, 'percentage': 0.0}
        
        # Load template
        doc = DocxTemplate(self.template_path)
        
        # Generate and add chart image using PERCENTAGES (not raw scores)
        # Writing score is already a percentage - use it directly
        scores = {
            "Reading": context["rc"]["percentage"],
            "Writing": context.get("writing_percentage", context.get("writing_score", 0.0)),
            "QR": context["qr"]["percentage"],
            "AR": context["ar"]["percentage"],
            "Total": context.get("total_score", 0.0),
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
        
        # Disable autofit for all tables to prevent automatic cell width adjustments
        # and stabilize the 4-column concept tables
        for table in doc.tables:
            table.autofit = False
            # Set preferred width if available
            try:
                if hasattr(table, 'width'):
                    table.width = Inches(6.5)  # Standard page width minus margins
            except:
                pass
        
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
    
    def generate_chart_bytes(
        self,
        student_data: Dict[str, Any],
        flow_type: str = "standard",
        analysis: Optional[FullAnalysis] = None,
    ) -> bytes:
        """
        Generate a performance chart and return as PNG bytes.
        
        Args:
            student_data: Dictionary containing student information and scores
            flow_type: One of 'mock', 'standard', or 'batch'
            analysis: Optional FullAnalysis object for mastery calculation
            
        Returns:
            Bytes of the generated PNG image
        """
        # Validate and normalize flow_type
        try:
            flow = FlowType(flow_type.lower())
        except ValueError:
            logger.warning(f"Unknown flow_type '{flow_type}', defaulting to 'standard'")
            flow = FlowType.STANDARD
        
        # Build context to get scores
        if analysis is not None:
            context = self._build_context_from_analysis(analysis, student_data, flow)
        else:
            context = self._build_context_from_dict(student_data, flow)
        
        # Extract scores for chart (use percentages, same as embedded chart)
        scores = {
            "Reading": context["rc"]["percentage"],
            "Writing": context.get("writing_percentage", context.get("writing_score", 0.0)),
            "QR": context["qr"]["percentage"],
            "AR": context["ar"]["percentage"],
            "Total": context.get("total_score", 0.0),
        }
        
        # Generate chart
        chart_buffer = self._create_bar_chart(
            context["student_name"],
            scores,
        )
        
        return chart_buffer.getvalue()
