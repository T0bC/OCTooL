"""
Unit tests for app/logic/rexview/export_worker.py

Tests the top-level, picklable worker used for process-based parallel export.
"""

import pickle
import queue
import threading
from unittest.mock import patch

import pytest

from app.logic.rexview import export_worker
from app.logic.rexview.export_worker import export_one_file
from app.logic.rexview.models import ExportConfig, ExportResult, SliceExportParams


@pytest.fixture
def params():
    return SliceExportParams(
        file_path="C:/data/scan.oct",
        name="TestScan",
        first_slice=1,
        last_slice=10,
        num_slices=5,
        slice_direction="XZ",
        db_min=20,
        db_max=80,
        refractive_index=1.0,
        dispersion=("None", "0"),
    )


@pytest.fixture
def config():
    return ExportConfig()


class TestExportOneFile:
    @pytest.mark.unit
    def test_export_one_file_is_picklable(self):
        """GIVEN the worker fn, WHEN pickled, THEN it round-trips (Windows spawn safe)."""
        restored = pickle.loads(pickle.dumps(export_one_file))
        assert restored is export_one_file

    @pytest.mark.unit
    def test_export_one_file_returns_result(self, params, config):
        """GIVEN a successful export, WHEN export_one_file runs, THEN returns the ExportResult."""
        fake_result = ExportResult(
            file_path=params.file_path,
            exported_files=["a.tiff", "b.tiff", "c.tiff"],
            failed_count=params.num_slices - 3,
            error=None,
        )
        with patch(
            "app.logic.rexview.export_worker.ExportService.run_export",
            return_value=fake_result,
        ):
            result = export_one_file(params.file_path, params, config)

        assert isinstance(result, ExportResult)
        assert result.file_path == params.file_path
        assert result.exported_files == ["a.tiff", "b.tiff", "c.tiff"]
        assert all(isinstance(f, str) for f in result.exported_files)
        assert result.failed_count == params.num_slices - 3
        assert result.error is None

    @pytest.mark.unit
    def test_export_one_file_is_picklable_result(self, params, config):
        """GIVEN a result, WHEN pickled, THEN it round-trips (cross-process return)."""
        fake_result = ExportResult(file_path=params.file_path, exported_files=["a.tiff"])
        with patch(
            "app.logic.rexview.export_worker.ExportService.run_export",
            return_value=fake_result,
        ):
            result = export_one_file(params.file_path, params, config)

        restored = pickle.loads(pickle.dumps(result))
        assert restored.exported_files == ["a.tiff"]

    @pytest.mark.unit
    def test_export_one_file_captures_error(self, params, config):
        """GIVEN run_export raises, WHEN export_one_file runs, THEN error is captured, no crash."""
        with patch(
            "app.logic.rexview.export_worker.ExportService.run_export",
            side_effect=RuntimeError("boom"),
        ):
            result = export_one_file(params.file_path, params, config)

        assert isinstance(result, ExportResult)
        assert result.exported_files == []
        assert result.error is not None
        assert "boom" in result.error


@pytest.fixture
def clean_worker_state():
    yield
    export_worker.reset_worker_state()


class TestWorkerState:
    @pytest.mark.unit
    def test_report_slice_without_queue_is_noop(self, clean_worker_state):
        export_worker.report_slice("a.oct", 1, 2)  # must not raise

    @pytest.mark.unit
    def test_report_slice_puts_message(self, clean_worker_state):
        q = queue.Queue()
        export_worker.init_worker(q, threading.Event(), None)
        export_worker.report_slice("a.oct", 1, 2)
        assert q.get_nowait() == ("a.oct", 1, 2)

    @pytest.mark.unit
    def test_init_worker_applies_thread_limit(self, clean_worker_state):
        with patch("threadpoolctl.threadpool_limits") as limits:
            export_worker.init_worker(None, None, 3)
        limits.assert_called_once_with(limits=3)

    @pytest.mark.unit
    def test_already_cancelled_returns_cancelled_without_exporting(
        self, params, config, clean_worker_state
    ):
        event = threading.Event()
        event.set()
        export_worker.init_worker(None, event, None)
        with patch("app.logic.rexview.export_worker.ExportService.run_export") as run:
            result = export_one_file(params.file_path, params, config)
        run.assert_not_called()
        assert result.cancelled

    @pytest.mark.unit
    def test_worker_passes_callbacks_to_service(self, params, config, clean_worker_state):
        q = queue.Queue()
        event = threading.Event()
        export_worker.init_worker(q, event, None)

        def fake_run(self, file_path, params, config, slice_callback=None, should_cancel=None):
            slice_callback(1, 5)
            assert should_cancel() is False
            event.set()
            assert should_cancel() is True
            return ExportResult(file_path=file_path, cancelled=True)

        with patch("app.logic.rexview.export_worker.ExportService.run_export", fake_run):
            result = export_one_file(params.file_path, params, config)

        assert q.get_nowait() == (params.file_path, 1, 5)
        assert result.cancelled
