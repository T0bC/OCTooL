"""
Unit tests for app/logic/rexview/export_worker.py

Tests the top-level, picklable worker used for process-based parallel export.
"""
import pickle
from pathlib import Path
from unittest.mock import patch

import pytest

from app.logic.rexview.export_worker import export_one_file
from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportResult


@pytest.fixture
def params():
    return SliceExportParams(
        file_path='C:/data/scan.oct',
        name='TestScan',
        first_slice=1,
        last_slice=10,
        num_slices=5,
        slice_direction='XZ',
        db_min=20,
        db_max=80,
        refractive_index=1.0,
        dispersion=('None', '0'),
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
            exported_files=['a.tiff', 'b.tiff', 'c.tiff'],
            failed_count=params.num_slices - 3,
            error=None,
        )
        with patch(
            'app.logic.rexview.export_worker.ExportService.run_export',
            return_value=fake_result,
        ):
            result = export_one_file(params.file_path, params, config)

        assert isinstance(result, ExportResult)
        assert result.file_path == params.file_path
        assert result.exported_files == ['a.tiff', 'b.tiff', 'c.tiff']
        assert all(isinstance(f, str) for f in result.exported_files)
        assert result.failed_count == params.num_slices - 3
        assert result.error is None

    @pytest.mark.unit
    def test_export_one_file_is_picklable_result(self, params, config):
        """GIVEN a result, WHEN pickled, THEN it round-trips (cross-process return)."""
        fake_result = ExportResult(file_path=params.file_path, exported_files=['a.tiff'])
        with patch(
            'app.logic.rexview.export_worker.ExportService.run_export',
            return_value=fake_result,
        ):
            result = export_one_file(params.file_path, params, config)

        restored = pickle.loads(pickle.dumps(result))
        assert restored.exported_files == ['a.tiff']

    @pytest.mark.unit
    def test_export_one_file_captures_error(self, params, config):
        """GIVEN run_export raises, WHEN export_one_file runs, THEN error is captured, no crash."""
        with patch(
            'app.logic.rexview.export_worker.ExportService.run_export',
            side_effect=RuntimeError('boom'),
        ):
            result = export_one_file(params.file_path, params, config)

        assert isinstance(result, ExportResult)
        assert result.exported_files == []
        assert result.error is not None
        assert 'boom' in result.error
