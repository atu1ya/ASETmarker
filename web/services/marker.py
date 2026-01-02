"""
Marking service that wraps the existing OMR logic.
STUB IMPLEMENTATION - Full implementation in Milestone 2.
"""
from pathlib import Path
import numpy as np


class MarkingService:
    """Service for processing OMR sheets and extracting responses."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.reading_template = None
        self.qrar_template = None

    def initialize_templates(self) -> None:
        """Load OMR templates from config directory."""
        # STUB - will load actual templates in M2
        return None

    def mark_reading_sheet(self, image_bytes: bytes, answer_key: list[str]) -> dict:
        """
        Process a reading sheet and return results.

        Returns:
            dict with keys:
            - responses: dict[str, str] - detected answers per question
            - results: dict - scoring results
            - marked_image: np.ndarray - annotated image
            - multi_marked: bool - whether multi-marking detected
        """
        # STUB - return dummy data for testing UI
        num_questions = len(answer_key)
        responses = {f"q{i + 1}": answer_key[i] for i in range(num_questions)}

        return {
            "responses": responses,
            "results": {
                "subject": "Reading",
                "correct": num_questions,
                "total": num_questions,
                "percentage": 100.0,
                "questions": [
                    {
                        "question": f"q{i + 1}",
                        "student_answer": answer_key[i],
                        "correct_answer": answer_key[i],
                        "is_correct": True,
                    }
                    for i in range(num_questions)
                ],
            },
            "marked_image": np.zeros((100, 100), dtype=np.uint8),
            "multi_marked": False,
        }

    def mark_qrar_sheet(self, image_bytes: bytes, answer_key: list[str]) -> dict:
        """Process a QR/AR sheet and return results."""
        # STUB - similar to reading
        num_questions = len(answer_key)

        # Split into QR and AR (assuming first 25 are QR, rest are AR)
        qr_count = min(25, num_questions)
        ar_count = num_questions - qr_count

        return {
            "qr": {
                "subject": "Quantitative Reasoning",
                "correct": qr_count,
                "total": qr_count,
                "percentage": 100.0,
                "questions": [
                    {
                        "question": f"qr{i + 1}",
                        "student_answer": answer_key[i],
                        "correct_answer": answer_key[i],
                        "is_correct": True,
                    }
                    for i in range(qr_count)
                ],
            },
            "ar": {
                "subject": "Abstract Reasoning",
                "correct": ar_count,
                "total": ar_count,
                "percentage": 100.0,
                "questions": [
                    {
                        "question": f"ar{i + 1}",
                        "student_answer": answer_key[qr_count + i],
                        "correct_answer": answer_key[qr_count + i],
                        "is_correct": True,
                    }
                    for i in range(ar_count)
                ],
            },
            "marked_image": np.zeros((100, 100), dtype=np.uint8),
            "multi_marked": False,
        }
