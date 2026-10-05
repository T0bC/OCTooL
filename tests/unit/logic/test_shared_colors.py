"""
Unit tests for app.logic.shared.colors.py
"""

import pytest

from app.logic.shared.colors import (
    choose_font_color,
    hex_to_rgb,
    hex_to_rgba,
    luminance,
    rgb_to_hex,
)


class TestHexToRgb:
    @pytest.mark.unit
    def test_uppercase_hex(self):
        """GIVEN an uppercase hex string, WHEN hex_to_rgb, THEN the (R, G, B) tuple is returned."""
        assert hex_to_rgb("#FF8000") == (255, 128, 0)

    @pytest.mark.unit
    def test_lowercase_hex(self):
        """GIVEN a lowercase hex string, WHEN hex_to_rgb, THEN the (R, G, B) tuple is returned."""
        assert hex_to_rgb("#00ff88") == (0, 255, 136)

    @pytest.mark.unit
    def test_leading_hash_optional(self):
        """GIVEN a hex string without '#', WHEN hex_to_rgb, THEN it is still parsed."""
        assert hex_to_rgb("FF0000") == (255, 0, 0)

    @pytest.mark.unit
    @pytest.mark.parametrize("bad", ["red", "#fff", "#12345", "#1234567", "#GG0000", "", None])
    def test_invalid_without_default_raises(self, bad):
        """GIVEN an invalid color and no default, WHEN hex_to_rgb, THEN ValueError is raised."""
        with pytest.raises(ValueError):
            hex_to_rgb(bad)

    @pytest.mark.unit
    @pytest.mark.parametrize("bad", ["red", "#fff", "#GG0000", "", None])
    def test_invalid_with_default_returns_default(self, bad):
        """GIVEN an invalid color and a default, WHEN hex_to_rgb, THEN the default is returned."""
        assert hex_to_rgb(bad, default=(1, 2, 3)) == (1, 2, 3)


class TestHexToRgba:
    @pytest.mark.unit
    def test_default_alpha_is_opaque(self):
        """GIVEN '#FF8000', WHEN hex_to_rgba, THEN returns (255, 128, 0, 255)."""
        assert hex_to_rgba("#FF8000") == (255, 128, 0, 255)

    @pytest.mark.unit
    def test_custom_alpha(self):
        """GIVEN alpha=128, WHEN hex_to_rgba, THEN the alpha channel is 128."""
        assert hex_to_rgba("#000000", alpha=128) == (0, 0, 0, 128)

    @pytest.mark.unit
    def test_invalid_with_default_appends_alpha(self):
        """GIVEN a bad color and an RGB default, WHEN hex_to_rgba, THEN default + alpha."""
        assert hex_to_rgba("notacolor", alpha=100, default=(255, 255, 178)) == (255, 255, 178, 100)

    @pytest.mark.unit
    def test_invalid_without_default_raises(self):
        """GIVEN a bad color and no default, WHEN hex_to_rgba, THEN ValueError is raised."""
        with pytest.raises(ValueError):
            hex_to_rgba("notacolor")


class TestRgbToHex:
    @pytest.mark.unit
    def test_lowercase_output(self):
        """GIVEN RGB values, WHEN rgb_to_hex, THEN a lowercase hex string is returned."""
        assert rgb_to_hex(255, 0, 0) == "#ff0000"
        assert rgb_to_hex(0, 255, 136) == "#00ff88"

    @pytest.mark.unit
    def test_round_trip(self):
        """GIVEN a hex color, WHEN round-tripping through RGB, THEN the value is preserved."""
        original = "#e600e6"
        assert rgb_to_hex(*hex_to_rgb(original)) == original


class TestLuminance:
    @pytest.mark.unit
    def test_white_is_bright(self):
        """GIVEN white, WHEN luminance, THEN ~1.0."""
        assert luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.unit
    def test_black_is_dark(self):
        """GIVEN black, WHEN luminance, THEN 0.0."""
        assert luminance("#000000") == pytest.approx(0.0, abs=1e-6)


class TestChooseFontColor:
    @pytest.mark.unit
    def test_dark_bg_white_font(self):
        """GIVEN dark background, WHEN choose_font_color, THEN white."""
        assert choose_font_color("#000000") == "#FFFFFF"

    @pytest.mark.unit
    def test_light_bg_black_font(self):
        """GIVEN light background, WHEN choose_font_color, THEN black."""
        assert choose_font_color("#FFFFFF") == "#000000"
