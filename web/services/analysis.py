"""
Analysis service for calculating strengths and weaknesses.
STUB IMPLEMENTATION - Full implementation in Milestone 2.
"""


class AnalysisService:
    """Analyzes student performance by learning area."""

    STRENGTH_THRESHOLD = 51  # percentage

    def __init__(self, concept_mapping: dict):
        self.concept_mapping = self._clean_mapping(concept_mapping)

    def _clean_mapping(self, mapping: dict) -> dict:
        """Remove instruction keys (starting with _)."""
        return {key: value for key, value in mapping.items() if not key.startswith("_")}

    def analyze_performance(self, subject: str, question_results: list[dict]) -> dict:
        """
        Analyze performance by learning area.

        Returns:
            dict with keys:
            - strengths: list[str] - areas with >= 51% correct
            - improvements: list[str] - areas with < 51% correct
            - details: list[dict] - per-area breakdown
        """
        if subject not in self.concept_mapping:
            return {"strengths": [], "improvements": [], "details": []}

        results_lookup = {result["question"]: result["is_correct"] for result in question_results}

        strengths: list[str] = []
        improvements: list[str] = []
        details: list[dict] = []

        for area, questions in self.concept_mapping[subject].items():
            correct = sum(1 for question in questions if results_lookup.get(question, False))
            total = len(questions)
            percentage = (correct / total * 100) if total > 0 else 0

            details.append(
                {
                    "area": area,
                    "correct": correct,
                    "total": total,
                    "percentage": round(percentage, 1),
                }
            )

            if percentage >= self.STRENGTH_THRESHOLD:
                strengths.append(area)
            else:
                improvements.append(area)

        return {
            "strengths": strengths,
            "improvements": improvements,
            "details": details,
        }

    def generate_full_analysis(
        self,
        reading_results: dict,
        qr_results: dict,
        ar_results: dict,
        writing_score: int,
    ) -> dict:
        """Generate complete analysis across all subjects."""
        return {
            "Reading": self.analyze_performance("Reading", reading_results.get("questions", [])),
            "Quantitative Reasoning": self.analyze_performance(
                "Quantitative Reasoning", qr_results.get("questions", [])
            ),
            "Abstract Reasoning": self.analyze_performance(
                "Abstract Reasoning", ar_results.get("questions", [])
            ),
            "Writing": {
                "score": writing_score,
                "note": "Manually assessed",
            },
        }
