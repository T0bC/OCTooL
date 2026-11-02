"""
Unit tests for app/logic/scanalign/matching_service.py

Tests the linked-scrolling index arithmetic without GUI dependencies.
"""

import pytest

from app.logic.scanalign.matching_service import compute_offset, linked_index


class TestComputeOffset:
    """Tests for compute_offset."""

    @pytest.mark.unit
    def test_positive_offset(self):
        """GIVEN scan 2 ahead of scan 1, WHEN computing, THEN delta is positive."""
        assert compute_offset(10, 28) == 18

    @pytest.mark.unit
    def test_negative_offset(self):
        """GIVEN scan 2 behind scan 1, WHEN computing, THEN delta is negative."""
        assert compute_offset(28, 10) == -18

    @pytest.mark.unit
    def test_zero_offset(self):
        """GIVEN equal positions, WHEN computing, THEN delta is zero."""
        assert compute_offset(5, 5) == 0


class TestLinkedIndex:
    """Tests for linked_index."""

    @pytest.mark.unit
    def test_scan1_to_scan2_adds_offset(self):
        """GIVEN delta 18, WHEN scan 1 moves, THEN scan 2 target is source + delta."""
        assert linked_index(10, 18, 900, source_is_scan1=True) == (28, True)

    @pytest.mark.unit
    def test_scan2_to_scan1_subtracts_offset(self):
        """GIVEN delta 18, WHEN scan 2 moves, THEN scan 1 target is source - delta."""
        assert linked_index(28, 18, 700, source_is_scan1=False) == (10, True)

    @pytest.mark.unit
    def test_clamps_at_upper_end(self):
        """GIVEN a target beyond the end, WHEN mapping, THEN it is clamped and out of range."""
        assert linked_index(690, 18, 700, source_is_scan1=True) == (699, False)

    @pytest.mark.unit
    def test_clamps_at_lower_end(self):
        """GIVEN a target below zero, WHEN mapping, THEN it is clamped to 0 and out of range."""
        assert linked_index(5, 18, 700, source_is_scan1=False) == (0, False)

    @pytest.mark.unit
    def test_last_valid_index_is_in_range(self):
        """GIVEN a target exactly at the last index, WHEN mapping, THEN it is in range."""
        assert linked_index(681, 18, 700, source_is_scan1=True) == (699, True)

    @pytest.mark.unit
    def test_zero_offset_maps_identically(self):
        """GIVEN delta 0, WHEN mapping either way, THEN the index is unchanged."""
        assert linked_index(7, 0, 20, source_is_scan1=True) == (7, True)
        assert linked_index(7, 0, 20, source_is_scan1=False) == (7, True)

    @pytest.mark.unit
    def test_empty_target(self):
        """GIVEN an empty target stack, WHEN mapping, THEN index 0 and out of range."""
        assert linked_index(3, 0, 0, source_is_scan1=True) == (0, False)
