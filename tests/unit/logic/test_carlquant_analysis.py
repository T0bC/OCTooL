"""
Unit tests for app/logic/carlquant/analysis_service.py.

Focus on the service contract (the per-slice pipeline extracted from
run_carl_quant): surface detection, the no-region placeholder path, image
loading, sequential iteration, progress callbacks, and cancellation.
"""
import numpy as np
import pytest
from PIL import Image

from app.logic.carlquant.analysis_service import AnalysisService, SliceAnalysis
from app.logic.carlquant.models import Surface, RegionConfig, LesionDepth


@pytest.fixture
def bright_band_image() -> np.ndarray:
    """A dark image with a bright horizontal band (a detectable surface)."""
    img = np.full((256, 256), 10, dtype=np.uint8)
    img[100:105, :] = 220  # bright surface band across all columns
    return img


@pytest.fixture
def lesion_image() -> np.ndarray:
    """Bright surface band plus an exponentially decaying subsurface profile.

    Gives surface detection a band to lock onto and lesion-depth detection a
    realistic decaying A-scan to analyse across the whole width.
    """
    h, w = 256, 256
    img = np.full((h, w), 10, dtype=np.uint8)
    surface_y = 100
    img[surface_y:surface_y + 5, :] = 230  # surface band
    depths = np.arange(h - (surface_y + 5))
    profile = (200 * np.exp(-depths / 25.0)).astype(np.uint8)
    img[surface_y + 5:, :] = np.clip(profile[:, None] + 10, 0, 255)
    return img


@pytest.fixture
def full_width_region() -> RegionConfig:
    """A region config spanning the full image width."""
    return RegionConfig(
        slice_index=0,
        specimen_start=(5, 100),
        lesion_start=(80, 100),
        lesion_end=(180, 100),
        tooth_end=(250, 100),
        is_keyframe=True,
    )


def _flat_surface(x_start: int, x_end: int, y: int = 100) -> Surface:
    """Build a Surface with a flat fitted actual_surface curve."""
    curve = [(x, y) for x in range(x_start, x_end)]
    return Surface(raw_points=curve, fitted_curves={"actual_surface": curve})


class TestDetectSurface:
    @pytest.mark.unit
    def test_returns_surface_object(self, bright_band_image):
        """GIVEN an image, WHEN detect_surface, THEN a Surface is returned."""
        surface = AnalysisService.detect_surface(bright_band_image)
        assert isinstance(surface, Surface)

    @pytest.mark.unit
    def test_detects_points_on_bright_band(self, bright_band_image):
        """GIVEN a clear bright band, WHEN detect_surface, THEN surface points exist."""
        surface = AnalysisService.detect_surface(bright_band_image)
        assert len(surface.raw_points) > 0

    @pytest.mark.unit
    def test_handles_flat_image_without_error(self):
        """GIVEN a featureless image, WHEN detect_surface, THEN no crash."""
        flat = np.full((128, 128), 50, dtype=np.uint8)
        surface = AnalysisService.detect_surface(flat)
        assert isinstance(surface, Surface)


class TestAnalyzeSliceNoRegion:
    @pytest.mark.unit
    def test_returns_placeholder_region_stats(self, bright_band_image):
        """GIVEN no region config, WHEN analyze_slice, THEN placeholder stats are returned."""
        result = AnalysisService.analyze_slice(
            bright_band_image, region_config=None, air_config=None,
            num_sound=3, num_lesion=4, slice_index=7,
        )
        assert isinstance(result, SliceAnalysis)
        assert result.slice_index == 7
        assert len(result.region_stats) == 7  # 3 sound + 4 lesion
        sound = [r for r in result.region_stats if r.region_type == "sound"]
        lesion = [r for r in result.region_stats if r.region_type == "lesion"]
        assert len(sound) == 3
        assert len(lesion) == 4

    @pytest.mark.unit
    def test_lesion_depth_none_without_region(self, bright_band_image):
        """GIVEN no region config, WHEN analyze_slice, THEN lesion_depth is None."""
        result = AnalysisService.analyze_slice(
            bright_band_image, region_config=None, air_config=None,
        )
        assert result.lesion_depth is None
        assert isinstance(result.surface, Surface)


class TestAnalyzeImage:
    @pytest.mark.unit
    def test_loads_image_from_disk(self, bright_band_image, tmp_path):
        """GIVEN an image file, WHEN analyze_image, THEN it loads and analyses it."""
        path = tmp_path / "tooth_005.png"
        Image.fromarray(bright_band_image, mode="L").save(path)
        result = AnalysisService.analyze_image(
            path, region_config=None, air_config=None, slice_index=5,
        )
        assert isinstance(result, SliceAnalysis)
        assert result.slice_index == 5
        assert len(result.surface.raw_points) > 0


class TestAnalyzeSlices:
    @pytest.mark.unit
    def test_iterates_all_tasks(self, bright_band_image, tmp_path):
        """GIVEN several tasks, WHEN analyze_slices, THEN one result per task."""
        paths = []
        for i in range(3):
            p = tmp_path / f"slice_{i}.png"
            Image.fromarray(bright_band_image, mode="L").save(p)
            paths.append(p)
        tasks = [(i, paths[i], None, None) for i in range(3)]

        results = AnalysisService.analyze_slices(tasks)
        assert len(results) == 3
        assert [r.slice_index for r in results] == [0, 1, 2]

    @pytest.mark.unit
    def test_progress_callback_invoked_per_slice(self, bright_band_image, tmp_path):
        """GIVEN a progress callback, WHEN analyze_slices, THEN it fires per slice."""
        p = tmp_path / "s.png"
        Image.fromarray(bright_band_image, mode="L").save(p)
        tasks = [(i, p, None, None) for i in range(2)]
        calls = []

        AnalysisService.analyze_slices(
            tasks, progress_callback=lambda done, total, idx: calls.append((done, total, idx))
        )
        assert calls == [(1, 2, 0), (2, 2, 1)]

    @pytest.mark.unit
    def test_cancellation_stops_early(self, bright_band_image, tmp_path):
        """GIVEN a cancel predicate, WHEN it trips, THEN iteration stops early."""
        p = tmp_path / "s.png"
        Image.fromarray(bright_band_image, mode="L").save(p)
        tasks = [(i, p, None, None) for i in range(5)]
        processed = {"count": 0}

        def progress(done, total, idx):
            processed["count"] = done

        # Cancel after the first slice completes.
        def is_cancelled():
            return processed["count"] >= 1

        results = AnalysisService.analyze_slices(
            tasks, progress_callback=progress, is_cancelled=is_cancelled
        )
        assert len(results) == 1


class TestComputeDelegators:
    @pytest.mark.unit
    def test_extract_regions_delegator(self, lesion_image, full_width_region):
        """GIVEN a surface + region, WHEN extract_regions, THEN stats are returned."""
        surface = _flat_surface(5, 250)
        stats = AnalysisService.extract_regions(
            lesion_image, surface, full_width_region,
            num_sound_regions=4, num_lesion_regions=4,
        )
        assert isinstance(stats, list)
        assert len(stats) > 0

    @pytest.mark.unit
    def test_extract_regions_without_fitted_curve_returns_empty(self, lesion_image, full_width_region):
        """GIVEN a surface lacking actual_surface, WHEN extract_regions, THEN empty list."""
        empty_surface = Surface(raw_points=[], fitted_curves={})
        stats = AnalysisService.extract_regions(
            lesion_image, empty_surface, full_width_region,
        )
        assert stats == []

    @pytest.mark.unit
    def test_calculate_lesion_depth_delegator(self, lesion_image, full_width_region):
        """GIVEN a surface + region, WHEN calculate_lesion_depth, THEN a result returns."""
        surface = _flat_surface(5, 250)
        depth = AnalysisService.calculate_lesion_depth(
            surface, full_width_region, lesion_image,
        )
        assert depth is None or isinstance(depth, LesionDepth)


class TestAnalyzeSliceWithRegion:
    @pytest.mark.unit
    def test_region_path_extracts_regions_and_depth(self, lesion_image, full_width_region):
        """GIVEN a region config, WHEN analyze_slice, THEN regions + depth are computed."""
        result = AnalysisService.analyze_slice(
            lesion_image, region_config=full_width_region, air_config=None,
            num_sound=4, num_lesion=4, slice_index=2,
        )
        assert isinstance(result, SliceAnalysis)
        assert len(result.region_stats) > 0
        assert result.lesion_depth is None or isinstance(result.lesion_depth, LesionDepth)
