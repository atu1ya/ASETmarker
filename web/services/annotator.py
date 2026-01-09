"""
Annotated sheet generation service.
Generates feedback sheets with:
- Correct answers: No annotation (clean)
- Incorrect answers: Red rectangle highlighting the correct option
"""
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from typing import Any, Union, List
from web.services.marker import SubjectResult, MarkingResult, QRARMarkingResult, QuestionResult


# Red color in BGR for OpenCV
CLR_RED = (0, 0, 255)


class AnnotatorService:
    """Generates annotated marked sheets highlighting correct/incorrect answers."""

    def _get_questions(self, result) -> List[QuestionResult]:
        """Get question results from either SubjectResult or MarkingResult."""
        # SubjectResult uses 'results', MarkingResult uses 'questions'
        if hasattr(result, 'results') and result.results:
            return result.results
        elif hasattr(result, 'questions') and result.questions:
            return result.questions
        return []

    def _get_score_total(self, result):
        """Get score and total from either SubjectResult or MarkingResult."""
        # SubjectResult: score, total_questions
        # MarkingResult: correct, total
        if hasattr(result, 'score'):
            score = result.score
        elif hasattr(result, 'correct'):
            score = result.correct
        else:
            score = 0
        
        if hasattr(result, 'total_questions'):
            total = result.total_questions
        elif hasattr(result, 'total'):
            total = result.total
        else:
            questions = self._get_questions(result)
            total = len(questions) if questions else 0
        
        return score, total

    def _find_bubble_for_answer(self, template, field_label: str, correct_value: str):
        """
        Find the bubble coordinates for a given field_label and correct_value.
        Returns (x, y, box_w, box_h, shift) or None if not found.
        """
        if template is None:
            return None
        
        for field_block in template.field_blocks:
            shift = field_block.shift
            box_w, box_h = field_block.bubble_dimensions
            
            for field_block_bubbles in field_block.traverse_bubbles:
                for bubble in field_block_bubbles:
                    # Match field_label and field_value (case-insensitive)
                    if (bubble.field_label.upper() == field_label.upper() and 
                        str(bubble.field_value).upper() == str(correct_value).upper()):
                        return (bubble.x, bubble.y, box_w, box_h, shift)
        
        return None

    def annotate_sheet(self, result: Union[SubjectResult, MarkingResult]) -> np.ndarray:
        """
        Annotates the sheet with feedback:
        - Correct answers: No annotation
        - Incorrect answers: Red rectangle around the correct option
        
        Returns the annotated image as np.ndarray.
        """
        if result.marked_image is None:
            raise ValueError("No marked image found in result.")
        
        img = result.marked_image.copy()
        
        # Convert to BGR for color annotation
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        template = getattr(result, 'template', None)
        questions = self._get_questions(result)
        
        # Iterate through question results
        for question in questions:
            if question.is_correct:
                # Correct answer: no annotation needed
                continue
            
            # Incorrect answer: highlight the correct option in red
            bubble_info = self._find_bubble_for_answer(
                template, 
                question.label, 
                question.correct_value
            )
            
            if bubble_info:
                x, y, box_w, box_h, shift = bubble_info
                # Apply shift from alignment
                x_shifted = x + shift
                
                # Draw red rectangle around the correct answer bubble
                cv2.rectangle(
                    img,
                    (int(x_shifted + box_w / 12), int(y + box_h / 12)),
                    (int(x_shifted + box_w - box_w / 12), int(y + box_h - box_h / 12)),
                    CLR_RED,
                    3
                )
        
        # Add score overlay
        img = self._add_score_overlay(img, result)
        
        return img

    def annotate_qrar_sheet(self, result: QRARMarkingResult) -> np.ndarray:
        """
        Annotates a QRAR sheet with feedback for both QR and AR sections.
        Returns the annotated image as np.ndarray.
        """
        if result.marked_image is None:
            raise ValueError("No marked image found in QRARMarkingResult.")
        
        img = result.marked_image.copy()
        
        # Convert to BGR for color annotation
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        template = getattr(result, 'template', None)
        
        # Process QR questions
        if result.qr:
            qr_questions = self._get_questions(result.qr)
            for question in qr_questions:
                if question.is_correct:
                    continue
                
                bubble_info = self._find_bubble_for_answer(
                    template,
                    question.label,
                    question.correct_value
                )
                
                if bubble_info:
                    x, y, box_w, box_h, shift = bubble_info
                    x_shifted = x + shift
                    cv2.rectangle(
                        img,
                        (int(x_shifted + box_w / 12), int(y + box_h / 12)),
                        (int(x_shifted + box_w - box_w / 12), int(y + box_h - box_h / 12)),
                        CLR_RED,
                        3
                    )
        
        # Process AR questions
        if result.ar:
            ar_questions = self._get_questions(result.ar)
            for question in ar_questions:
                if question.is_correct:
                    continue
                
                bubble_info = self._find_bubble_for_answer(
                    template,
                    question.label,
                    question.correct_value
                )
                
                if bubble_info:
                    x, y, box_w, box_h, shift = bubble_info
                    x_shifted = x + shift
                    cv2.rectangle(
                        img,
                        (int(x_shifted + box_w / 12), int(y + box_h / 12)),
                        (int(x_shifted + box_w - box_w / 12), int(y + box_h - box_h / 12)),
                        CLR_RED,
                        3
                    )
        
        # Add score overlay for combined result
        img = self._add_qrar_score_overlay(img, result)
        
        return img

    def _add_score_overlay(self, img: np.ndarray, result: Union[SubjectResult, MarkingResult]) -> np.ndarray:
        """Add score text overlay to the image."""
        h, w = img.shape[:2]
        
        score, total = self._get_score_total(result)
        
        text = f"Score: {score} / {total}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 3
        text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_w, text_h = text_size
        
        # Position: top-right with margin
        pad_x, pad_y = 20, 20
        x = w - text_w - pad_x
        y = pad_y + text_h
        
        # Draw white rectangle background
        rect_x1 = x - 10
        rect_y1 = y - text_h - 10
        rect_x2 = x + text_w + 10
        rect_y2 = y + 10
        cv2.rectangle(img, (rect_x1, rect_y1), (rect_x2, rect_y2), (255, 255, 255), -1)
        cv2.rectangle(img, (rect_x1, rect_y1), (rect_x2, rect_y2), (52, 152, 219), 3)
        cv2.putText(img, text, (x, y), font, font_scale, (44, 62, 80), thickness, cv2.LINE_AA)
        
        return img

    def _add_qrar_score_overlay(self, img: np.ndarray, result: QRARMarkingResult) -> np.ndarray:
        """Add combined QR/AR score overlay to the image."""
        h, w = img.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        
        lines = []
        if result.qr:
            qr_score, qr_total = self._get_score_total(result.qr)
            lines.append(f"QR: {qr_score} / {qr_total}")
        if result.ar:
            ar_score, ar_total = self._get_score_total(result.ar)
            lines.append(f"AR: {ar_score} / {ar_total}")
        
        if not lines:
            return img
        
        # Calculate text dimensions
        max_text_w = 0
        total_text_h = 0
        line_heights = []
        for line in lines:
            text_size, _ = cv2.getTextSize(line, font, font_scale, thickness)
            max_text_w = max(max_text_w, text_size[0])
            line_heights.append(text_size[1])
            total_text_h += text_size[1] + 10
        
        # Position: top-right with margin
        pad_x, pad_y = 20, 20
        x = w - max_text_w - pad_x
        y_start = pad_y
        
        # Draw background
        rect_x1 = x - 10
        rect_y1 = y_start
        rect_x2 = x + max_text_w + 10
        rect_y2 = y_start + total_text_h + 10
        cv2.rectangle(img, (rect_x1, rect_y1), (rect_x2, rect_y2), (255, 255, 255), -1)
        cv2.rectangle(img, (rect_x1, rect_y1), (rect_x2, rect_y2), (52, 152, 219), 3)
        
        # Draw text lines
        y = y_start + line_heights[0] + 5
        for i, line in enumerate(lines):
            cv2.putText(img, line, (x, y), font, font_scale, (44, 62, 80), thickness, cv2.LINE_AA)
            if i + 1 < len(line_heights):
                y += line_heights[i + 1] + 10
        
        return img

    def image_to_pdf_bytes(self, img: np.ndarray) -> bytes:
        """
        Converts an annotated image (np.ndarray) to PDF bytes.
        """
        # Ensure RGB for PIL
        if len(img.shape) == 2:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        else:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        buffer = BytesIO()
        pil_img.save(buffer, format="PDF")
        return buffer.getvalue()
