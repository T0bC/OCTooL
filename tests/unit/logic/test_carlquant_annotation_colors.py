"""
Unit tests for app/logic/carlquant/annotation_colors.py.

Covers the colour constants (conversion helpers live in app/logic/shared/colors.py).
"""

import pytest

from app.logic.carlquant import annotation_colors as ac


@pytest.mark.unit
def test_color_constants_are_defined():
    """Sanity-check that the documented color constants exist and are strings."""
    for name in (
        "INTERPOLATED_SURFACE_COLOR",
        "ACTUAL_SURFACE_COLOR",
        "LESION_DEPTH_PRIMARY_COLOR",
        "EXTRACTION_REGION_COLOR",
        "AIR_REGION_COLOR",
        "HALF_SPAN_POINT_COLOR",
    ):
        assert isinstance(getattr(ac, name), str)


@pytest.mark.unit
def test_component_method_colors_are_distinct():
    """Each depth method needs its own colour to be readable when overlaid."""
    colors = [
        ac.KNEE_POINT_COLOR,
        ac.INFLECTION_POINT_COLOR,
        ac.SHOULDER_POINT_COLOR,
        ac.HALF_SPAN_POINT_COLOR,
    ]
    assert len(set(colors)) == len(colors)
