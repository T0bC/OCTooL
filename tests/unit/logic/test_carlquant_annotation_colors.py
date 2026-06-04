"""
Unit tests for app/logic/carlquant/annotation_colors.py.

Covers the hex/named color conversion helpers, including the named-color
passthrough branch and the round-trip between hex_to_rgb and rgb_to_hex.
"""
import pytest

from app.logic.carlquant import annotation_colors as ac


@pytest.mark.unit
def test_hex_to_rgb_basic():
    """GIVEN a hex string, WHEN converting, THEN the (R, G, B) tuple is returned."""
    assert ac.hex_to_rgb("#FF0000") == (255, 0, 0)
    assert ac.hex_to_rgb("#00ff88") == (0, 255, 136)


@pytest.mark.unit
def test_hex_to_rgb_named_color_passthrough():
    """GIVEN a named color (no '#'), WHEN converting, THEN it is returned unchanged."""
    assert ac.hex_to_rgb("red") == "red"
    assert ac.hex_to_rgb("cyan") == "cyan"


@pytest.mark.unit
def test_rgb_to_hex_basic():
    """GIVEN RGB values, WHEN converting, THEN a lowercase hex string is returned."""
    assert ac.rgb_to_hex(255, 0, 0) == "#ff0000"
    assert ac.rgb_to_hex(0, 255, 136) == "#00ff88"


@pytest.mark.unit
def test_hex_rgb_round_trip():
    """GIVEN a hex color, WHEN round-tripping through RGB, THEN the value is preserved."""
    original = "#e600e6"
    r, g, b = ac.hex_to_rgb(original)
    assert ac.rgb_to_hex(r, g, b) == original


@pytest.mark.unit
def test_color_constants_are_defined():
    """Sanity-check that the documented color constants exist and are strings."""
    for name in (
        "INTERPOLATED_SURFACE_COLOR",
        "ACTUAL_SURFACE_COLOR",
        "LESION_DEPTH_PRIMARY_COLOR",
        "EXTRACTION_REGION_COLOR",
        "AIR_REGION_COLOR",
    ):
        assert isinstance(getattr(ac, name), str)
