from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
from dotmap import DotMap

# --- Legacy OMR Engine Imports ---
from src.defaults import CONFIG_DEFAULTS
from src.template import Template
from src.core import ImageInstanceOps
from src.utils.parsing import get_concatenated_response
from src.processors.FeatureBasedAlignment import FeatureBasedAlignment

# Register FeatureBasedAlignment (required for templates)
from src.processors import manager as processor_manager
processor_manager.PROCESSOR_MANAGER.processors["FeatureBasedAlignment"] = FeatureBasedAlignment

@dataclass
class QuestionResult:
    label: str
    marked_value: str
    correct_value: str
    is_correct: bool

@dataclass
class SubjectResult:
    subject_name: str
    score: int
    total_questions: int
    results: List[QuestionResult]
    omr_response: Dict[str, str]
    marked_image: Any = field(repr=False)

class MarkingService:
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.tuning_config = DotMap(CONFIG_DEFAULTS)
        self.tuning_config.outputs.save_image_level = 0  # Prevent disk writes

    def process_single_subject(
        self,
        image_bytes: bytes,
        answer_key: Dict[str, str],
        template_filename: str,
        subject_name: str = "OMR"
    ) -> SubjectResult:
        # Decode image bytes to grayscale
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Could not decode image bytes to a valid grayscale image.")

        # Template path
        template_path = self.config_dir / template_filename
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        # Load Template
        template = Template(template_path, self.tuning_config)

        # ImageInstanceOps
        ops = ImageInstanceOps(self.tuning_config)

        # Preprocess
        processed_image = ops.apply_preprocessors("dummy_path", image, template)

        # OMR Response
        omr_response, final_marked, multi_marked, multi_roll = ops.read_omr_response(
            template, processed_image, "dummy_name"
        )

        # Normalize output
        clean_response = get_concatenated_response(omr_response, template)

        # Scoring
        results: List[QuestionResult] = []
        correct = 0
        for label, correct_value in answer_key.items():
            marked_value = clean_response.get(label, "")
            is_correct = (marked_value == correct_value)
            if is_correct:
                correct += 1
            results.append(QuestionResult(
                label=label,
                marked_value=marked_value,
                correct_value=correct_value,
                is_correct=is_correct
            ))

        return SubjectResult(
            subject_name=subject_name,
            score=correct,
            total_questions=len(answer_key),
            results=results,
            omr_response=clean_response,
            marked_image=final_marked
        )


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
