"""
Unit tests for app/logic/carlquant/interpolation_service.py.

Keyframe interpolation behaviour: single-keyframe propagation, linear
interpolation between keyframes, backfill, and forward-fill.
"""
import pytest

from app.logic.carlquant.interpolation_service import (
    InterpolationService,
    REGION_DESCRIPTOR,
)
from app.logic.carlquant.models import RegionConfig, AirConfig


def _region(slice_index, x, *, keyframe=False):
    """Build a RegionConfig with all four points at column x (y fixed)."""
    return RegionConfig(
        slice_index=slice_index,
        specimen_start=(x, 10),
        lesion_start=(x + 10, 10),
        lesion_end=(x + 20, 10),
        tooth_end=(x + 30, 10),
        is_keyframe=keyframe,
    )


def _collect(config_dict, total_slices):
    """Run region interpolation, writing results back into config_dict."""
    def update(idx, cfg, is_keyframe):
        # Reconstruct so the stored slice_index reflects its own slot.
        config_dict[idx] = RegionConfig(
            slice_index=idx,
            specimen_start=cfg.specimen_start,
            lesion_start=cfg.lesion_start,
            lesion_end=cfg.lesion_end,
            tooth_end=cfg.tooth_end,
            is_keyframe=is_keyframe,
        )
    InterpolationService.interpolate_regions(config_dict, total_slices, update)
    return config_dict


class TestSingleKeyframe:
    @pytest.mark.unit
    def test_propagates_to_all_slices(self):
        """GIVEN one keyframe, WHEN interpolating, THEN all slices share its coords."""
        configs = {2: _region(2, 100, keyframe=True)}
        result = _collect(configs, total_slices=5)
        assert set(result.keys()) == {0, 1, 2, 3, 4}
        for idx in range(5):
            assert result[idx].specimen_start == (100, 10)
        # Non-keyframe slices are marked as propagated.
        assert result[2].is_keyframe is True
        assert result[0].is_keyframe is False


class TestMultipleKeyframes:
    @pytest.mark.unit
    def test_linear_interpolation_midpoint(self):
        """GIVEN keyframes at 0 and 2, WHEN interpolating, THEN slice 1 is the midpoint."""
        configs = {
            0: _region(0, 0, keyframe=True),
            2: _region(2, 100, keyframe=True),
        }
        result = _collect(configs, total_slices=3)
        # specimen_start x interpolated halfway between 0 and 100.
        assert result[1].specimen_start == (50, 10)
        assert result[1].is_keyframe is False

    @pytest.mark.unit
    def test_backfill_before_first_keyframe(self):
        """GIVEN first keyframe at 2, WHEN interpolating, THEN earlier slices copy it."""
        configs = {
            2: _region(2, 100, keyframe=True),
            4: _region(4, 200, keyframe=True),
        }
        result = _collect(configs, total_slices=5)
        assert result[0].specimen_start == (100, 10)
        assert result[1].specimen_start == (100, 10)

    @pytest.mark.unit
    def test_forward_fill_after_last_keyframe(self):
        """GIVEN last keyframe at 2, WHEN interpolating, THEN later slices copy it."""
        configs = {
            0: _region(0, 0, keyframe=True),
            2: _region(2, 100, keyframe=True),
        }
        result = _collect(configs, total_slices=5)
        assert result[3].specimen_start == (100, 10)
        assert result[4].specimen_start == (100, 10)


class TestEdgeCases:
    @pytest.mark.unit
    def test_empty_dict_is_noop(self):
        """GIVEN no configs, WHEN interpolating, THEN nothing is added."""
        configs = {}
        _collect(configs, total_slices=5)
        assert configs == {}

    @pytest.mark.unit
    def test_no_keyframes_is_noop(self):
        """GIVEN only non-keyframes, WHEN interpolating, THEN dict is unchanged."""
        configs = {1: _region(1, 50, keyframe=False)}
        _collect(configs, total_slices=5)
        assert set(configs.keys()) == {1}

    @pytest.mark.unit
    def test_generic_interpolate_with_descriptor(self):
        """GIVEN keyframes + descriptor, WHEN generic interpolate, THEN gap is filled."""
        configs = {
            0: _region(0, 0, keyframe=True),
            2: _region(2, 100, keyframe=True),
        }

        def update(idx, cfg, is_keyframe):
            configs[idx] = RegionConfig(
                slice_index=idx,
                specimen_start=cfg.specimen_start,
                lesion_start=cfg.lesion_start,
                lesion_end=cfg.lesion_end,
                tooth_end=cfg.tooth_end,
                is_keyframe=is_keyframe,
            )

        InterpolationService.interpolate(configs, 3, REGION_DESCRIPTOR, update)
        assert configs[1].specimen_start == (50, 10)

    @pytest.mark.unit
    def test_air_interpolation_optional_point2(self):
        """GIVEN AIR keyframes, WHEN interpolating, THEN point1 interpolates linearly."""
        configs = {
            0: AirConfig(slice_index=0, point1=(0, 0), point2=(10, 10), is_keyframe=True),
            2: AirConfig(slice_index=2, point1=(100, 100), point2=(110, 110), is_keyframe=True),
        }

        def update(idx, cfg, is_keyframe):
            configs[idx] = AirConfig(
                slice_index=idx,
                point1=cfg.point1,
                point2=cfg.point2,
                is_keyframe=is_keyframe,
            )

        InterpolationService.interpolate_air(configs, total_slices=3, update_func=update)
        assert configs[1].point1 == (50, 50)
        assert configs[1].point2 == (60, 60)

    @pytest.mark.unit
    def test_adjacent_keyframes_skip_interpolation(self):
        """GIVEN adjacent keyframes (no gap), WHEN interpolating, THEN no slice is created between them."""
        configs = {
            0: _region(0, 0, keyframe=True),
            1: _region(1, 100, keyframe=True),  # adjacent to slice 0 -> nothing to interpolate
            3: _region(3, 300, keyframe=True),
        }
        result = _collect(configs, total_slices=4)
        # Slice 2 lies in the gap between keyframes 1 and 3 and is interpolated.
        assert result[2].is_keyframe is False
        # The adjacent pair (0, 1) keeps both original keyframe values.
        assert result[0].specimen_start == (0, 10)
        assert result[1].specimen_start == (100, 10)

    @pytest.mark.unit
    def test_air_optional_point2_present_only_in_start(self):
        """GIVEN start has point2 but end does not, WHEN interpolating, THEN start's point2 is kept."""
        configs = {
            0: AirConfig(slice_index=0, point1=(0, 0), point2=(10, 10), is_keyframe=True),
            2: AirConfig(slice_index=2, point1=(100, 100), point2=None, is_keyframe=True),
        }

        def update(idx, cfg, is_keyframe):
            configs[idx] = AirConfig(
                slice_index=idx,
                point1=cfg.point1,
                point2=cfg.point2,
                is_keyframe=is_keyframe,
            )

        InterpolationService.interpolate_air(configs, total_slices=3, update_func=update)
        assert configs[1].point1 == (50, 50)
        # end point2 is None -> start's point2 is carried forward unchanged.
        assert configs[1].point2 == (10, 10)

    @pytest.mark.unit
    def test_air_optional_point2_absent_in_start(self):
        """GIVEN start lacks point2, WHEN interpolating, THEN the interpolated point2 is None."""
        configs = {
            0: AirConfig(slice_index=0, point1=(0, 0), point2=None, is_keyframe=True),
            2: AirConfig(slice_index=2, point1=(100, 100), point2=(110, 110), is_keyframe=True),
        }

        def update(idx, cfg, is_keyframe):
            configs[idx] = AirConfig(
                slice_index=idx,
                point1=cfg.point1,
                point2=cfg.point2,
                is_keyframe=is_keyframe,
            )

        InterpolationService.interpolate_air(configs, total_slices=3, update_func=update)
        assert configs[1].point1 == (50, 50)
        assert configs[1].point2 is None
