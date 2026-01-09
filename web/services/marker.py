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
    template: Any = field(repr=False, default=None)  # Template object for annotation

@dataclass
class QRARMarkingResult:
    success: bool
    qr: Optional[MarkingResult] = None
    ar: Optional[MarkingResult] = None
    marked_image: Optional[np.ndarray] = field(repr=False, default=None)
    multi_marked: bool = False
    error: Optional[str] = None
    template: Any = field(repr=False, default=None)  # Template object for annotation

import cv2
import numpy as np
from dotmap import DotMap

# --- Legacy OMR Engine Imports ---
from src.defaults import CONFIG_DEFAULTS
from src.template import Template
from src.core import ImageInstanceOps
from src.utils.parsing import get_concatenated_response
from src.processors.FeatureBasedAlignment import FeatureBasedAlignment
from src.processors.CropOnMarkers import CropOnMarkers
from src.processors.CropPage import CropPage

# Register preprocessors (required for templates)
from src.processors import manager as processor_manager
processor_manager.PROCESSOR_MANAGER.processors["FeatureBasedAlignment"] = FeatureBasedAlignment
processor_manager.PROCESSOR_MANAGER.processors["CropOnMarkers"] = CropOnMarkers
processor_manager.PROCESSOR_MANAGER.processors["CropPage"] = CropPage

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
    template: Any = field(repr=False, default=None)  # Template object for annotation

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

    def _run_omr_pipeline(self, image: np.ndarray, template: Template) -> Tuple[dict, np.ndarray, bool, Any, np.ndarray]:
        ops = ImageInstanceOps(self.tuning_config)
        processed_image = ops.apply_preprocessors("dummy_path", image, template)
        omr_response, final_marked, multi_marked, multi_roll, clean_img = ops.read_omr_response(
            template, processed_image, "dummy_name"
        )
        return omr_response, final_marked, multi_marked, multi_roll, clean_img

    def _normalize_marked_value(self, value: Any) -> str:
        """
        Normalize a marked value to a string for comparison.
        Handles lists (e.g., ['A']), strings, and other types.
        """
        if value is None:
            return ""
        if isinstance(value, list):
            if len(value) == 0:
                return ""
            elif len(value) == 1:
                # Single selection - extract the value
                return str(value[0]).strip().upper()
            else:
                # Multiple selections - join them (multi-marked)
                return ",".join(str(v).strip().upper() for v in sorted(value))
        return str(value).strip().upper()

    def _lookup_response(self, clean_response: dict, label: str) -> Any:
        """
        Look up a response value, trying multiple key variations.
        E.g., for label "RC1", try: "RC1", "rc1", "1", "q1"
        """
        # Try exact match first
        if label in clean_response:
            return clean_response[label]
        
        # Try case-insensitive match
        label_lower = label.lower()
        label_upper = label.upper()
        for key in clean_response:
            if key.lower() == label_lower or key.upper() == label_upper:
                return clean_response[key]
        
        # Try extracting number and matching with different prefixes
        import re
        match = re.search(r'(\d+)$', label)
        if match:
            num = match.group(1)
            # Try just the number
            if num in clean_response:
                return clean_response[num]
            # Try common prefixes
            for prefix in ['q', 'Q', 'rc', 'RC', 'qr', 'QR', 'ar', 'AR']:
                alt_key = f"{prefix}{num}"
                if alt_key in clean_response:
                    return clean_response[alt_key]
        
        return ""

    def _evaluate_responses(self, clean_response: dict, answer_key: dict) -> Tuple[List[QuestionResult], int]:
        results: List[QuestionResult] = []
        correct = 0
        for label, correct_value in answer_key.items():
            raw_marked = self._lookup_response(clean_response, label)
            marked_normalized = self._normalize_marked_value(raw_marked)
            correct_normalized = str(correct_value).strip().upper()
            
            # Handle multi-marked case: if marked has multiple values, it's incorrect
            is_multi = "," in marked_normalized
            is_correct = (marked_normalized == correct_normalized) and not is_multi
            
            if is_correct:
                correct += 1
            
            # Store the normalized marked value for display
            display_marked = marked_normalized if marked_normalized else "(blank)"
            
            results.append(QuestionResult(
                label=label,
                marked_value=display_marked,
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
        omr_response, final_marked, multi_marked, _, clean_img = self._run_omr_pipeline(image, template)
        clean_response = get_concatenated_response(omr_response, template)
        results, correct = self._evaluate_responses(clean_response, answer_key)
        return SubjectResult(
            subject_name=subject_name,
            score=correct,
            total_questions=len(answer_key),
            results=results,
            omr_response=clean_response,
            marked_image=clean_img,  # Use clean image instead of final_marked
            template=template  # Pass template for annotation
        )


    def mark_reading_sheet(self, image_bytes: bytes, answer_key: List[str], template_filename: str = "reading_template.json") -> MarkingResult:
        """
        Process a reading sheet and return a MarkingResult dataclass.
        """
        try:
            self._validate_image(image_bytes)
            image = self._bytes_to_cv_image(image_bytes)
            template = self._load_template(template_filename)
            omr_response, final_marked, multi_marked, _, clean_img = self._run_omr_pipeline(image, template)
            clean_response = get_concatenated_response(omr_response, template)
            # Map answer_key to dict using RC prefix to match template fieldLabels
            if isinstance(answer_key, list):
                answer_key_dict = {f"RC{i+1}": v for i, v in enumerate(answer_key)}
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
                marked_image=clean_img,  # Use clean image instead of final_marked
                multi_marked=multi_marked,
                template=template  # Pass template for annotation
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
            omr_response, final_marked, multi_marked, _, clean_img = self._run_omr_pipeline(image, template)
            clean_response = get_concatenated_response(omr_response, template)
            # Split answer_key into QR and AR (first 35 QR, rest AR) - using uppercase prefixes to match template
            num_questions = len(answer_key)
            qr_count = min(35, num_questions)
            ar_count = num_questions - qr_count
            qr_key = {f"QR{i+1}": answer_key[i] for i in range(qr_count)}
            ar_key = {f"AR{i+1}": answer_key[qr_count + i] for i in range(ar_count)}
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
                marked_image=clean_img,  # Use clean image
                multi_marked=multi_marked,
                template=template  # Pass template
            )
            ar_result = MarkingResult(
                success=True,
                subject="Abstract Reasoning",
                correct=ar_correct,
                total=ar_total,
                percentage=ar_percentage,
                questions=ar_results,
                responses=clean_response,
                marked_image=clean_img,  # Use clean image
                multi_marked=multi_marked,
                template=template  # Pass template
            )
            return QRARMarkingResult(
                success=True,
                qr=qr_result,
                ar=ar_result,
                marked_image=clean_img,  # Use clean image
                multi_marked=multi_marked,
                template=template  # Pass template
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
