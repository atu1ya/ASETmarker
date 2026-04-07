from __future__ import annotations

import numpy as np

from desktop.services.annotator import AnnotatorService


def test_qrar_score_badges_keep_full_page_and_draw_top_and_bottom_right() -> None:
    service = AnnotatorService()
    base = np.full((1000, 700, 3), 255, dtype=np.uint8)

    result = service.format_qrar_sections(
        base.copy(),
        template=None,
        qr_score=18,
        qr_total=35,
        ar_score=22,
        ar_total=35,
    )

    # Must preserve original page dimensions (no split/stack formatting).
    assert result.shape == base.shape

    # Score badge in top-right region should alter pixels from white.
    top_right_roi = result[10:180, 450:690]
    assert np.any(top_right_roi < 255)

    # AR badge should appear in top-right of lower half.
    lower_half_top_right_roi = result[520:700, 450:690]
    assert np.any(lower_half_top_right_roi < 255)
