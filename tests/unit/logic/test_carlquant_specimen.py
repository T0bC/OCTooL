"""
Unit tests for AnalysisService.analyze_specimen.

Exercises the whole-specimen pipeline extracted from run_carl_quant: sequential
processing, result storage, status setting, progress/mode callbacks, and
cooperative cancellation. Saving is disabled (``save=False``) to keep tests fast
and tkinter/Excel free; the persistence path is covered by DataSaver tests.
"""
import threading

import numpy as np
import pytest
from PIL import Image

from app.logic.carlquant.analysis_service import AnalysisService, SpecimenAnalysisResult
from app.logic.carlquant.models import (
    Specimen,
    SpecimenConfig,
    RegionConfig,
)


def _make_specimen(tmp_path, n_slices: int, *, with_config: bool = False) -> Specimen:
    """Create a Specimen backed by n bright-band PNG slices on disk."""
    img = np.full((128, 128), 10, dtype=np.uint8)
    img[60:65, :] = 220
    paths = []
    for i in range(n_slices):
        p = tmp_path / f"tooth_{i:03d}.png"
        Image.fromarray(img, mode="L").save(p)
        paths.append(p)
    specimen = Specimen(
        specimen_id="S1",
        source=tmp_path,
        images=paths,
        slices=n_slices,
        status="Pending",
        date=0.0,
    )
    if with_config:
        config = SpecimenConfig(specimen_id="S1")
        for i in range(n_slices):
            config.regions[i] = RegionConfig(
                slice_index=i,
                specimen_start=(5, 60),
                lesion_start=(40, 60),
                lesion_end=(90, 60),
                tooth_end=(120, 60),
                is_keyframe=True,
            )
        specimen.config = config
    specimen.operator = "OP"
    specimen.measurement = 1
    return specimen


class TestSequentialAnalysis:
    @pytest.mark.unit
    def test_processes_all_slices_and_completes(self, tmp_path):
        """GIVEN a 3-slice specimen, WHEN analyzed, THEN all slices stored + Completed."""
        specimen = _make_specimen(tmp_path, 3)
        result = AnalysisService.analyze_specimen(
            specimen, num_sound=2, num_lesion=2, save=False,
        )
        assert isinstance(result, SpecimenAnalysisResult)
        assert result.status == "Completed"
        assert result.processed_count == 3
        assert result.total_slices == 3
        assert result.saved is False
        assert len(specimen.results) == 3
        assert specimen.status == "Completed"

    @pytest.mark.unit
    def test_reports_sequential_mode(self, tmp_path):
        """GIVEN few slices, WHEN analyzed, THEN on_mode reports sequential."""
        specimen = _make_specimen(tmp_path, 2)
        modes = []
        AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=False,
            on_mode=lambda mode, workers: modes.append((mode, workers)),
        )
        assert modes == [("sequential", 1)]

    @pytest.mark.unit
    def test_slice_progress_callback(self, tmp_path):
        """GIVEN a progress callback, WHEN analyzed, THEN it fires once per slice."""
        specimen = _make_specimen(tmp_path, 3)
        calls = []
        AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=False,
            on_slice_done=lambda done, total: calls.append((done, total)),
        )
        assert calls == [(0, 3), (1, 3), (2, 3)]


class TestCancellation:
    @pytest.mark.unit
    def test_cancel_before_any_slice(self, tmp_path):
        """GIVEN immediate cancel, WHEN analyzed, THEN status Cancelled, nothing stored."""
        specimen = _make_specimen(tmp_path, 3)
        result = AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=False,
            is_cancelled=lambda: True,
        )
        assert result.status == "Cancelled"
        assert result.processed_count == 0
        assert specimen.results == {}

    @pytest.mark.unit
    def test_cancel_after_first_slice_is_partial(self, tmp_path):
        """GIVEN cancel after one slice, WHEN analyzed, THEN status Partial."""
        specimen = _make_specimen(tmp_path, 4)
        state = {"done": 0}

        def on_slice_done(done, total):
            state["done"] = done + 1

        def is_cancelled():
            return state["done"] >= 1

        result = AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=False,
            on_slice_done=on_slice_done, is_cancelled=is_cancelled,
        )
        assert result.status == "Partial"
        assert result.processed_count == 1


class TestRegionConfigPath:
    @pytest.mark.unit
    def test_uses_region_config_when_present(self, tmp_path):
        """GIVEN a specimen with region config, WHEN analyzed, THEN slices processed."""
        specimen = _make_specimen(tmp_path, 2, with_config=True)
        result = AnalysisService.analyze_specimen(
            specimen, num_sound=2, num_lesion=2, save=False,
        )
        assert result.status == "Completed"
        assert result.processed_count == 2
        # Real region stats were extracted (not just placeholders).
        assert len(specimen.results[0].region_stats) > 0

    @pytest.mark.unit
    def test_result_lock_is_used_for_thread_safe_store(self, tmp_path):
        """GIVEN a result_lock, WHEN analyzed, THEN storing acquires it per slice."""
        specimen = _make_specimen(tmp_path, 2)

        class CountingLock:
            def __init__(self):
                self.acquired = 0

            def __enter__(self):
                self.acquired += 1
                return self

            def __exit__(self, *exc):
                return False

        lock = CountingLock()
        AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=False, result_lock=lock,
        )
        assert lock.acquired == 2


class TestSavePath:
    @pytest.mark.unit
    def test_save_writes_files_and_clears_results(self, tmp_path):
        """GIVEN save=True, WHEN analyzed, THEN results persist and memory is cleared."""
        specimen = _make_specimen(tmp_path, 2)
        result = AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=True,
        )
        assert result.saved is True
        # Excel results file is written under Data_{operator}_{measurement}.
        data_dir = tmp_path / "Data_OP_1"
        assert data_dir.exists()
        assert any(data_dir.glob("*.xlsx"))
        # In-memory results are cleared after saving.
        assert specimen.results == {}


class TestParallelPath:
    @pytest.mark.slow
    @pytest.mark.unit
    def test_forced_parallel_processing(self, tmp_path):
        """GIVEN a low parallel threshold, WHEN analyzed, THEN the parallel path runs."""
        specimen = _make_specimen(tmp_path, 3)
        modes = []
        result = AnalysisService.analyze_specimen(
            specimen, num_sound=1, num_lesion=1, save=False,
            parallel_threshold=1, max_workers=2,
            on_mode=lambda mode, workers: modes.append(mode),
        )
        assert modes == ["parallel"]
        assert result.status == "Completed"
        assert result.processed_count == 3
