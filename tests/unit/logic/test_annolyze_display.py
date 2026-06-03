"""
Unit tests for app/logic/annolyze/display_service.py
"""
import pytest

from app.logic.annolyze.display_service import DisplayService


@pytest.fixture
def service():
    return DisplayService()


class TestLuminance:
    @pytest.mark.unit
    def test_white_is_bright(self, service):
        """GIVEN white, WHEN luminance, THEN ~1.0."""
        assert service.luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.unit
    def test_black_is_dark(self, service):
        """GIVEN black, WHEN luminance, THEN 0.0."""
        assert service.luminance("#000000") == pytest.approx(0.0, abs=1e-6)


class TestChooseFontColor:
    @pytest.mark.unit
    def test_dark_bg_white_font(self, service):
        """GIVEN dark background, WHEN choose_font_color, THEN white."""
        assert service.choose_font_color("#000000") == "#FFFFFF"

    @pytest.mark.unit
    def test_light_bg_black_font(self, service):
        """GIVEN light background, WHEN choose_font_color, THEN black."""
        assert service.choose_font_color("#FFFFFF") == "#000000"


class TestColumnWidth:
    @pytest.mark.unit
    def test_short_header_uses_min(self, service):
        """GIVEN short header, WHEN calculate_column_width, THEN at least base width."""
        assert service.calculate_column_width("A") >= 40

    @pytest.mark.unit
    def test_long_header_capped(self, service):
        """GIVEN very long header, WHEN calculate_column_width, THEN capped at 250."""
        assert service.calculate_column_width("X" * 200) == 250
