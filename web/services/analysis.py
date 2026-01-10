from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any
from .marker import SubjectResult
@dataclass
class SubjectAnalysis:
    subject: str
    area_results: List[LearningAreaResult]
    unmapped_questions: List[str] = field(default_factory=list)


@dataclass
class LearningAreaResult:
    area: str
    correct: int
    total: int
    percentage: float
    status: str  # "Done well" or "Needs improvement"
    question_numbers: str = ""  # Comma-separated question numbers (e.g., "1, 2, 5")

@dataclass
class FullAnalysis:
    subject_areas: Dict[str, List[LearningAreaResult]]
    summary: Dict[str, Any] = field(default_factory=dict)

class AnalysisService:
    THRESHOLD = 51.0

    def __init__(self, concept_map: Dict[str, Dict[str, List[str]]]):
        """
        concept_map: Dict[subject, Dict[area, List[question_label]]]
        """
        self.concept_map = concept_map

    def analyze_subject_performance(
        self,
        subject: str,
        question_results: List[Dict[str, Any]]
    ) -> SubjectAnalysis:
        # Helper function to normalize labels by extracting only digits
        def normalize_label(label: str) -> str:
            """Extract only numeric digits from label (e.g., 'RC1', 'q1', '1' -> '1')."""
            return ''.join(c for c in label if c.isdigit())
        
        # Build lookup for question correctness using normalized labels
        correct_lookup = {normalize_label(q["label"]): q["is_correct"] for q in question_results}
        
        subject_map = self.concept_map.get(subject, {})
        area_results: List[LearningAreaResult] = []
        mapped_questions = set()
        
        for area, questions in subject_map.items():
            total = len(questions)
            correct_count = 0
            question_nums = []
            
            for q in questions:
                normalized_q = normalize_label(q)
                question_nums.append(normalized_q)
                if correct_lookup.get(normalized_q, False):
                    correct_count += 1
            
            percentage = (correct_count / total * 100.0) if total > 0 else 0.0
            # Strictly follow the rule: >= 51.0 is "Done well"
            status = "Done well" if percentage >= self.THRESHOLD else "Needs improvement"
            
            # Create comma-separated string of question numbers
            question_numbers_str = ", ".join(question_nums)
            
            area_results.append(LearningAreaResult(
                area=area,
                correct=correct_count,
                total=total,
                percentage=percentage,
                status=status,
                question_numbers=question_numbers_str
            ))
            mapped_questions.update(questions)
        
        # Find unmapped questions
        all_labels = set(q["label"] for q in question_results)
        unmapped = list(all_labels - mapped_questions)
        
        return SubjectAnalysis(
            subject=subject,
            area_results=area_results,
            unmapped_questions=unmapped
        )


    def generate_full_analysis(
        self,
        reading: SubjectResult,
        qr: SubjectResult,
        ar: SubjectResult
    ) -> FullAnalysis:
        subject_areas = {}
        summary = {}
        for subj, result in zip([
            "Reading", "Quantitative Reasoning", "Abstract Reasoning"
        ], [reading, qr, ar]):
            analysis = self.analyze_subject_performance(subj, [
                {"label": q.label, "is_correct": q.is_correct} for q in result.results
            ])
            subject_areas[subj] = analysis.area_results
            summary[subj] = {
                "done_well": [a.area for a in analysis.area_results if a.status == "Done well"],
                "needs_improvement": [a.area for a in analysis.area_results if a.status == "Needs improvement"],
                "unmapped_questions": analysis.unmapped_questions
            }
        return FullAnalysis(subject_areas=subject_areas, summary=summary)

