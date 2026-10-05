"""
Unit tests for app.logic.shared.display_service.py
"""

import pytest

from app.logic.shared.display_service import DisplayService


@pytest.fixture
def service():
    return DisplayService()


class TestColumnWidth:
    @pytest.mark.unit
    def test_short_header_uses_min(self, service):
        """GIVEN short header, WHEN calculate_column_width, THEN at least base width."""
        assert service.calculate_column_width("A") >= 40

    @pytest.mark.unit
    def test_long_header_capped(self, service):
        """GIVEN very long header, WHEN calculate_column_width, THEN capped at 250."""
        assert service.calculate_column_width("X" * 200) == 250


class TestColumnWidthForContent:
    @pytest.mark.unit
    def test_header_longer_than_cells(self, service):
        """GIVEN header longer than cells, WHEN width for content, THEN header width wins."""
        assert service.calculate_column_width_for_content("Long header", ["a", "bb"]) == 11 * 7 + 20

    @pytest.mark.unit
    def test_cells_exceed_max_width(self, service):
        """GIVEN very long cell, WHEN width for content, THEN capped at 250."""
        assert service.calculate_column_width_for_content("A", ["x" * 200]) == 250
