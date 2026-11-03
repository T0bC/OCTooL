"""
Unit tests for app/logic/shared/slice_math.py

Tests the shared equidistant slice selection without GUI dependencies.
"""

import pytest

from app.logic.shared.slice_math import equidistant_indices


class TestEquidistantIndices:
    """Tests for equidistant_indices."""

    @pytest.mark.unit
    def test_zero_or_negative_n_returns_empty(self):
        """GIVEN n <= 0, WHEN selecting, THEN the result is empty."""
        assert equidistant_indices(1, 10, 0) == []
        assert equidistant_indices(1, 10, -3) == []

    @pytest.mark.unit
    def test_single_slice_is_midpoint(self):
        """GIVEN n == 1, WHEN selecting, THEN the range midpoint is returned."""
        assert equidistant_indices(1, 11, 1) == [6]

    @pytest.mark.unit
    def test_two_slices_are_the_endpoints(self):
        """GIVEN n == 2, WHEN selecting, THEN first and last are returned."""
        assert equidistant_indices(5, 105, 2) == [5, 105]

    @pytest.mark.unit
    def test_more_than_available_returns_all(self):
        """GIVEN n larger than the range, WHEN selecting, THEN every slice is returned."""
        assert equidistant_indices(3, 6, 10) == [3, 4, 5, 6]

    @pytest.mark.unit
    def test_integer_step(self):
        """GIVEN a range divisible by n-1, WHEN selecting, THEN the step is exact."""
        assert equidistant_indices(1, 101, 5) == [1, 26, 51, 76, 101]

    @pytest.mark.unit
    def test_non_integer_step_rounds(self):
        """GIVEN a non-integer step, WHEN selecting, THEN values are rounded not truncated."""
        # step = 10 / 3 = 3.333..; positions 1, 4.33, 7.67, 11
        assert equidistant_indices(1, 11, 4) == [1, 4, 8, 11]

    @pytest.mark.unit
    def test_endpoints_and_strictly_increasing(self):
        """GIVEN a typical range, WHEN selecting, THEN endpoints are exact and values rise."""
        result = equidistant_indices(12, 688, 25)
        assert len(result) == 25
        assert result[0] == 12
        assert result[-1] == 688
        assert all(a < b for a, b in zip(result, result[1:], strict=False))
