"""
Annotated sheet generation service.
STUB IMPLEMENTATION - Full implementation in Milestone 3.
"""
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from typing import Any
from web.services.marker import SubjectResult


class AnnotatorService:
    """Generates annotated marked sheets highlighting correct/incorrect answers."""


    def annotate_sheet(self, result: SubjectResult) -> np.ndarray:
        """
        Overlays the score on the marked image and returns the annotated image (np.ndarray).
        """
        if result.marked_image is None:
            raise ValueError("No marked image found in SubjectResult.")
        img = result.marked_image.copy()
        # Ensure 3 channels for color annotation
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w = img.shape[:2]
        text = f"Score: {result.score} / {result.total_questions}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 3
        text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_w, text_h = text_size
        # Padding around text
        pad_x, pad_y = 20, 20
        # Position: top-right with margin
        x = w - text_w - pad_x
        y = pad_y + text_h
        # Draw white rectangle for background
        rect_x1 = x - 10
        rect_y1 = y - text_h - 10
        rect_x2 = x + text_w + 10
        rect_y2 = y + 10
        cv2.rectangle(img, (rect_x1, rect_y1), (rect_x2, rect_y2), (255, 255, 255), -1)
        # Draw border (branding color)
        cv2.rectangle(img, (rect_x1, rect_y1), (rect_x2, rect_y2), (52, 152, 219), 3)
        # Put text (branding color)
        cv2.putText(img, text, (x, y), font, font_scale, (44, 62, 80), thickness, cv2.LINE_AA)
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
