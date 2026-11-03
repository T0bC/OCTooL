"""
Unit tests for app/logic/scanalign/matching_service.py

Tests the linked-scrolling and slice-pairing index arithmetic without GUI dependencies.
"""

from pathlib import Path

import pytest

from app.logic.scanalign.matching_service import (
    build_pairs,
    compute_offset,
    linked_index,
    max_pairs,
    pair_indices,
    range_linked_index,
    range_summary,
)
from app.logic.scanalign.models import ScanGeometry, SliceFile, SliceRange, StackInfo


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


def _stack(slice_numbers):
    folder = Path("/virtual/010RI/01_x_XZ")
    return StackInfo(
        folder=folder,
        specimen="010RI",
        name="x",
        exp_number=1,
        extension=".tiff",
        files=[
            SliceFile(
                path=folder / f"x_1_#{s}_{i + 1:04d}.tiff", slice_number=s, export_index=i + 1
            )
            for i, s in enumerate(slice_numbers)
        ],
        geometry=ScanGeometry(n_slices=len(slice_numbers), width_px=10, height_px=10),
    )


class TestMaxPairs:
    """Tests for max_pairs."""

    @pytest.mark.unit
    def test_is_the_shorter_range(self):
        """GIVEN ranges of different length, WHEN asking, THEN the shorter length is returned."""
        assert max_pairs(SliceRange(first=0, last=9), SliceRange(first=5, last=24)) == 10


class TestPairIndices:
    """Tests for pair_indices."""

    @pytest.mark.unit
    def test_exact_endpoints_and_strictly_increasing(self):
        """GIVEN two ranges, WHEN pairing, THEN endpoints are exact and positions rise."""
        r1, r2 = SliceRange(first=11, last=687), SliceRange(first=29, last=705)
        pairs = pair_indices(r1, r2, 25)
        assert len(pairs) == 25
        assert pairs[0] == (11, 29)
        assert pairs[-1] == (687, 705)
        assert all(a[0] < b[0] and a[1] < b[1] for a, b in zip(pairs, pairs[1:], strict=False))

    @pytest.mark.unit
    def test_ranges_of_different_length(self):
        """GIVEN ranges of different length, WHEN pairing, THEN each range spans its own ends."""
        r1, r2 = SliceRange(first=0, last=10), SliceRange(first=100, last=120)
        assert pair_indices(r1, r2, 3) == [(0, 100), (5, 110), (10, 120)]

    @pytest.mark.unit
    def test_n_equal_to_max_pairs_is_allowed(self):
        """GIVEN n == max_pairs, WHEN pairing, THEN every position of the shorter range is used."""
        r1, r2 = SliceRange(first=0, last=4), SliceRange(first=10, last=30)
        pairs = pair_indices(r1, r2, 5)
        assert [p[0] for p in pairs] == [0, 1, 2, 3, 4]

    @pytest.mark.unit
    @pytest.mark.parametrize("n", [-1, 0, 1])
    def test_too_few_raises(self, n):
        """GIVEN n < 2, WHEN pairing, THEN ValueError is raised."""
        with pytest.raises(ValueError):
            pair_indices(SliceRange(first=0, last=9), SliceRange(first=0, last=9), n)

    @pytest.mark.unit
    def test_too_many_raises(self):
        """GIVEN n > max_pairs, WHEN pairing, THEN ValueError is raised."""
        with pytest.raises(ValueError):
            pair_indices(SliceRange(first=0, last=9), SliceRange(first=0, last=19), 11)


class TestBuildPairs:
    """Tests for build_pairs."""

    @pytest.mark.unit
    def test_k_and_slice_numbers(self):
        """GIVEN stacks with slice numbers, WHEN building, THEN k is 1-based and numbers map."""
        s1 = _stack([10, 11, 12, 13])
        s2 = _stack([20, 21, 22, 23, 24])
        pairs = build_pairs(s1, s2, SliceRange(first=0, last=3), SliceRange(first=0, last=4), 2)
        assert [(p.k, p.index1, p.index2, p.slice1, p.slice2) for p in pairs] == [
            (1, 0, 0, 10, 20),
            (2, 3, 4, 13, 24),
        ]

    @pytest.mark.unit
    def test_unparsed_slice_number_falls_back_to_position(self):
        """GIVEN an unparsed file, WHEN building, THEN position + 1 is used."""
        s1 = _stack([1, 2, 3])
        s1.files[2] = SliceFile(path=Path("/virtual/odd.png"))
        s2 = _stack([5, 6, 7])
        pairs = build_pairs(s1, s2, SliceRange(first=0, last=2), SliceRange(first=0, last=2), 2)
        assert pairs[-1].slice1 == 3
        assert pairs[-1].slice2 == 7


class TestRangeSummary:
    """Tests for range_summary."""

    @pytest.mark.unit
    def test_offset_and_scale(self):
        """GIVEN two ranges, WHEN summarising, THEN offset and length ratio are returned."""
        offset, scale = range_summary(
            SliceRange(first=10, last=109), SliceRange(first=28, last=227)
        )
        assert offset == 18
        assert scale == pytest.approx(2.0)


class TestRangeLinkedIndex:
    """Tests for range_linked_index."""

    @pytest.mark.unit
    def test_identity_for_equal_ranges(self):
        """GIVEN identical ranges, WHEN mapping, THEN the index is unchanged."""
        r = SliceRange(first=5, last=15)
        assert range_linked_index(9, r, r, 100) == (9, True)

    @pytest.mark.unit
    def test_equal_length_behaves_like_offset(self):
        """GIVEN equal-length ranges, WHEN mapping, THEN it equals linked_index with delta."""
        r1, r2 = SliceRange(first=10, last=60), SliceRange(first=28, last=78)
        for s in (0, 10, 33, 60, 80):
            assert range_linked_index(s, r1, r2, 200) == linked_index(s, 18, 200, True)

    @pytest.mark.unit
    def test_scaling_for_different_lengths(self):
        """GIVEN a target range twice as long, WHEN mapping, THEN steps are doubled."""
        r1, r2 = SliceRange(first=10, last=20), SliceRange(first=100, last=120)
        assert range_linked_index(10, r1, r2, 500) == (100, True)
        assert range_linked_index(15, r1, r2, 500) == (110, True)
        assert range_linked_index(20, r1, r2, 500) == (120, True)

    @pytest.mark.unit
    def test_extrapolates_outside_range(self):
        """GIVEN a source outside its range, WHEN mapping, THEN the line is extrapolated."""
        r1, r2 = SliceRange(first=10, last=20), SliceRange(first=100, last=120)
        assert range_linked_index(5, r1, r2, 500) == (90, True)
        assert range_linked_index(25, r1, r2, 500) == (130, True)

    @pytest.mark.unit
    def test_clamps_at_both_ends(self):
        """GIVEN a mapped target outside the stack, WHEN mapping, THEN clamp and out of range."""
        r1, r2 = SliceRange(first=10, last=20), SliceRange(first=2, last=12)
        assert range_linked_index(0, r1, r2, 50) == (0, False)
        r3 = SliceRange(first=40, last=48)
        assert range_linked_index(30, r1, r3, 50) == (49, False)
