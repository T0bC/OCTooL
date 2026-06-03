"""
Unit tests for AnalysisService.analyze_specimen.

Exercises the whole-specimen pipeline extracted from run_carl_quant: sequential
processing, result storage, status setting, progress/mode callbacks, and
cooperative cancellation. Saving is disabled (``save=False``) to keep tests fast
and tkinter/Excel free; the persistence path is covered by DataSaver tests.
"""
import numpy as np
import pytest
from PIL import Image

from app.logic.carlquant.analysis_service import AnalysisService, SpecimenAnalysisResult
from app.logic.carlquant.models import Specimen


def _make_specimen(tmp_path, n_slices: int) -> Specimen:
    """Create a Specimen backed by n bright-band PNG slices on disk."""
    img = np.full((128, 128), 10, dtype=np.uint8)
    img[60:65, :] = 220
    paths = []
    for i in range(n_slices):
        p = tmp_path / f"tooth_{i:03d}.png"
        Image.fromarray(img, mode="L").save(p)
        paths.append(p)
    return Specimen(
        specimen_id="S1",
        source=tmp_path,
        images=paths,
        slices=n_slices,
        status="Pending",
        date=0.0,
    )


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
