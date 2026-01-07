from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any
from .marker import SubjectResult

@dataclass
class LearningAreaResult:
    area: str
    correct: int
    total: int
    percentage: float
    status: str  # "Done well" or "Needs improvement"

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

    def analyze_subject(
        self,
        subject: str,
        question_results: List[Dict[str, Any]]
    ) -> List[LearningAreaResult]:
        # Build lookup for question correctness
        correct_lookup = {q["label"]: q["is_correct"] for q in question_results}
        subject_map = self.concept_map.get(subject, {})
        area_results: List[LearningAreaResult] = []
        for area, questions in subject_map.items():
            total = len(questions)
            correct = sum(1 for q in questions if correct_lookup.get(q, False))
            percentage = (correct / total * 100.0) if total > 0 else 0.0
            status = "Done well" if percentage >= self.THRESHOLD else "Needs improvement"
            area_results.append(LearningAreaResult(
                area=area,
                correct=correct,
                total=total,
                percentage=percentage,
                status=status
            ))
        return area_results

    def compile_full_analysis(
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
            areas = self.analyze_subject(subj, [
                {"label": q.label, "is_correct": q.is_correct} for q in result.results
            ])
            subject_areas[subj] = areas
            summary[subj] = {
                "done_well": [a.area for a in areas if a.status == "Done well"],
                "needs_improvement": [a.area for a in areas if a.status == "Needs improvement"]
            }

        return FullAnalysis(subject_areas=subject_areas, summary=summary)

