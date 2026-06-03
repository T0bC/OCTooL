"""
Unit tests for app/logic/carlquant/models.py.

Verifies the logic-layer model surface (re-homed dataclasses + enum) and the
buffer-coordinate helpers on RegionConfig.
"""
import pytest

from app.logic.carlquant.models import (
    RegionConfig,
    AirConfig,
    SpecimenConfig,
    DepthDetectionMethod,
)


class TestRegionConfigBuffers:
    @pytest.mark.unit
    def test_buffered_lesion_start_moves_right(self):
        """GIVEN a region, WHEN buffered lesion start, THEN x shifts right by buffer."""
        cfg = RegionConfig(
            slice_index=0,
            specimen_start=(10, 100),
            lesion_start=(100, 100),
            lesion_end=(200, 100),
            tooth_end=(300, 100),
            buffer_pixels=10,
        )
        assert cfg.get_buffered_lesion_start_x() == 110

    @pytest.mark.unit
    def test_buffered_lesion_end_moves_left(self):
        """GIVEN a region, WHEN buffered lesion end, THEN x shifts left by buffer."""
        cfg = RegionConfig(
            slice_index=0,
            specimen_start=(10, 100),
            lesion_start=(100, 100),
            lesion_end=(200, 100),
            tooth_end=(300, 100),
            buffer_pixels=15,
        )
        assert cfg.get_buffered_lesion_end_x() == 185

    @pytest.mark.unit
    def test_buffered_sound_regions(self):
        """GIVEN a region, WHEN buffered sound bounds, THEN both shift away from lesion."""
        cfg = RegionConfig(
            slice_index=0,
            specimen_start=(10, 100),
            lesion_start=(100, 100),
            lesion_end=(200, 100),
            tooth_end=(300, 100),
            buffer_pixels=10,
        )
        assert cfg.get_buffered_sound_left_end_x() == 90
        assert cfg.get_buffered_sound_right_start_x() == 210

    @pytest.mark.unit
    def test_defaults(self):
        """GIVEN minimal args, WHEN constructed, THEN default flags apply."""
        cfg = RegionConfig(
            slice_index=3,
            specimen_start=(0, 0),
            lesion_start=(1, 1),
            lesion_end=(2, 2),
            tooth_end=(3, 3),
        )
        assert cfg.is_keyframe is False
        assert cfg.buffer_pixels == 10


class TestSpecimenConfig:
    @pytest.mark.unit
    def test_empty_collections_by_default(self):
        """GIVEN a SpecimenConfig, WHEN created, THEN regions/air are empty dicts."""
        cfg = SpecimenConfig(specimen_id="S1")
        assert cfg.regions == {}
        assert cfg.air == {}

    @pytest.mark.unit
    def test_holds_region_and_air(self):
        """GIVEN region + air configs, WHEN stored, THEN retrievable by slice index."""
        cfg = SpecimenConfig(specimen_id="S1")
        cfg.regions[0] = RegionConfig(
            slice_index=0,
            specimen_start=(0, 0), lesion_start=(1, 1),
            lesion_end=(2, 2), tooth_end=(3, 3),
        )
        cfg.air[0] = AirConfig(slice_index=0, point1=(5, 5), point2=(9, 9))
        assert cfg.regions[0].slice_index == 0
        assert cfg.air[0].point2 == (9, 9)


class TestDepthDetectionMethod:
    @pytest.mark.unit
    def test_default_is_combined_mean(self):
        """GIVEN the enum, WHEN get_default, THEN COMBINED_MEAN."""
        assert DepthDetectionMethod.get_default() is DepthDetectionMethod.COMBINED_MEAN

    @pytest.mark.unit
    def test_value_roundtrip(self):
        """GIVEN a method string, WHEN constructed, THEN matches enum value."""
        assert DepthDetectionMethod("knee_point") is DepthDetectionMethod.KNEE_POINT
        assert DepthDetectionMethod.SIGMOID_FIT.value == "sigmoid_fit"
