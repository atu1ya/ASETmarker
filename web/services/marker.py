from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Image format signatures for validation ---
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
JPEG_SIGNATURE = b'\xff\xd8\xff'

# --- MarkingResult and QRARMarkingResult ---
@dataclass
class MarkingResult:
    success: bool
    subject: str
    correct: int
    total: int
    percentage: float
    questions: List[QuestionResult]
    responses: Dict[str, str]
    marked_image: Optional[np.ndarray] = field(repr=False, default=None)
    multi_marked: bool = False
    error: Optional[str] = None

@dataclass
class QRARMarkingResult:
    success: bool
    qr: Optional[MarkingResult] = None
    ar: Optional[MarkingResult] = None
    marked_image: Optional[np.ndarray] = field(repr=False, default=None)
    multi_marked: bool = False
    error: Optional[str] = None

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


    def _validate_image(self, image_bytes: bytes) -> None:
        """Validate that the image is either PNG or JPEG format."""
        if not (image_bytes.startswith(PNG_SIGNATURE) or image_bytes.startswith(JPEG_SIGNATURE)):
            raise ValueError("Input image must be a valid PNG or JPEG file.")

    def _bytes_to_cv_image(self, image_bytes: bytes) -> np.ndarray:
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Could not decode image bytes to a valid grayscale image.")
        return image

    def _load_template(self, template_filename: str) -> Template:
        template_path = self.config_dir / template_filename
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        return Template(template_path, self.tuning_config)

    def _run_omr_pipeline(self, image: np.ndarray, template: Template) -> Tuple[dict, np.ndarray, bool, Any]:
        ops = ImageInstanceOps(self.tuning_config)
        processed_image = ops.apply_preprocessors("dummy_path", image, template)
        omr_response, final_marked, multi_marked, multi_roll = ops.read_omr_response(
            template, processed_image, "dummy_name"
        )
        return omr_response, final_marked, multi_marked, multi_roll

    def _evaluate_responses(self, clean_response: dict, answer_key: dict) -> Tuple[List[QuestionResult], int]:
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
        return results, correct

    def process_single_subject(
        self,
        image_bytes: bytes,
        answer_key: Dict[str, str],
        template_filename: str,
        subject_name: str = "OMR"
    ) -> SubjectResult:
        self._validate_image(image_bytes)
        image = self._bytes_to_cv_image(image_bytes)
        template = self._load_template(template_filename)
        omr_response, final_marked, multi_marked, _ = self._run_omr_pipeline(image, template)
        clean_response = get_concatenated_response(omr_response, template)
        results, correct = self._evaluate_responses(clean_response, answer_key)
        return SubjectResult(
            subject_name=subject_name,
            score=correct,
            total_questions=len(answer_key),
            results=results,
            omr_response=clean_response,
            marked_image=final_marked
        )


    def mark_reading_sheet(self, image_bytes: bytes, answer_key: List[str], template_filename: str = "reading_template.json") -> MarkingResult:
        """
        Process a reading sheet and return a MarkingResult dataclass.
        """
        try:
            self._validate_image(image_bytes)
            image = self._bytes_to_cv_image(image_bytes)
            template = self._load_template(template_filename)
            omr_response, final_marked, multi_marked, _ = self._run_omr_pipeline(image, template)
            clean_response = get_concatenated_response(omr_response, template)
            # Map answer_key to dict if needed
            if isinstance(answer_key, list):
                answer_key_dict = {f"q{i+1}": v for i, v in enumerate(answer_key)}
            else:
                answer_key_dict = answer_key
            results, correct = self._evaluate_responses(clean_response, answer_key_dict)
            total = len(answer_key_dict)
            percentage = (correct / total * 100.0) if total else 0.0
            return MarkingResult(
                success=True,
                subject="Reading",
                correct=correct,
                total=total,
                percentage=percentage,
                questions=results,
                responses=clean_response,
                marked_image=final_marked,
                multi_marked=multi_marked
            )
        except Exception as e:
            return MarkingResult(
                success=False,
                subject="Reading",
                correct=0,
                total=len(answer_key),
                percentage=0.0,
                questions=[],
                responses={},
                marked_image=None,
                multi_marked=False,
                error=str(e)
            )

    def mark_qrar_sheet(self, image_bytes: bytes, answer_key: List[str], template_filename: str = "qrar_template.json") -> QRARMarkingResult:
        """
        Process a QR/AR sheet and return a QRARMarkingResult dataclass.
        """
        try:
            self._validate_image(image_bytes)
            image = self._bytes_to_cv_image(image_bytes)
            template = self._load_template(template_filename)
            omr_response, final_marked, multi_marked, _ = self._run_omr_pipeline(image, template)
            clean_response = get_concatenated_response(omr_response, template)
            # Split answer_key into QR and AR (first 25 QR, rest AR)
            num_questions = len(answer_key)
            qr_count = min(25, num_questions)
            ar_count = num_questions - qr_count
            qr_key = {f"qr{i+1}": answer_key[i] for i in range(qr_count)}
            ar_key = {f"ar{i+1}": answer_key[qr_count + i] for i in range(ar_count)}
            qr_results, qr_correct = self._evaluate_responses(clean_response, qr_key)
            ar_results, ar_correct = self._evaluate_responses(clean_response, ar_key)
            qr_total = len(qr_key)
            ar_total = len(ar_key)
            qr_percentage = (qr_correct / qr_total * 100.0) if qr_total else 0.0
            ar_percentage = (ar_correct / ar_total * 100.0) if ar_total else 0.0
            qr_result = MarkingResult(
                success=True,
                subject="Quantitative Reasoning",
                correct=qr_correct,
                total=qr_total,
                percentage=qr_percentage,
                questions=qr_results,
                responses=clean_response,
                marked_image=final_marked,
                multi_marked=multi_marked
            )
            ar_result = MarkingResult(
                success=True,
                subject="Abstract Reasoning",
                correct=ar_correct,
                total=ar_total,
                percentage=ar_percentage,
                questions=ar_results,
                responses=clean_response,
                marked_image=final_marked,
                multi_marked=multi_marked
            )
            return QRARMarkingResult(
                success=True,
                qr=qr_result,
                ar=ar_result,
                marked_image=final_marked,
                multi_marked=multi_marked
            )
        except Exception as e:
            return QRARMarkingResult(
                success=False,
                qr=None,
                ar=None,
                marked_image=None,
                multi_marked=False,
                error=str(e)
            )
