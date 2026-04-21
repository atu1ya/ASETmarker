from desktop.services import marker as desktop_marker


def test_desktop_marker_registers_template_preprocessors() -> None:
    processors = desktop_marker.processor_manager.PROCESSOR_MANAGER.processors

    assert "FeatureBasedAlignment" in processors
    assert "CropOnMarkers" in processors
    assert "CropPage" in processors
    assert "Levels" in processors
    assert "GaussianBlur" in processors
    assert "MedianBlur" in processors
