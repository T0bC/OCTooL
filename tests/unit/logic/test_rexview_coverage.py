"""
Additional unit tests targeting previously-uncovered branches in the
app/logic/rexview services and models.

These tests focus on error paths, alternate slice directions, and the
end-to-end export pipeline that were not exercised by the existing suites.
"""
import pytest
import numpy as np
from PIL import Image
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.logic.rexview.export_service import ExportService
from app.logic.rexview.image_service import ImageService
from app.logic.rexview.queue_service import QueueService
from app.logic.rexview.settings_service import SettingsService
from app.logic.rexview.file_discovery_service import FileDiscoveryService
from app.view.rexview.gui_adapters import settings_config_from_gui_state
from app.logic.rexview.models import (
    ExportConfig,
    SliceExportParams,
    SettingsConfig,
    QueueItem,
    ImageDisplayConfig,
    ExportSettings,
)
from app.logic.shared.models import OCTMetadata


# ============================================================================
# ExportService
# ============================================================================

class TestExportServiceUncovered:
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)

    @pytest.fixture
    def config(self):
        return ExportConfig(resize_enabled=False, scale_enabled=False)

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_load_image_stack_delegates_to_octF(self, mock_octF, metadata, config):
        service = ExportService()
        params = SliceExportParams(
            file_path='C:/data/test.oct', name='S',
            first_slice=1, last_slice=10, num_slices=5,
        )
        sentinel = np.zeros((5, 8, 8), dtype=np.uint8)
        mock_octF.createImageFromRaw.return_value = sentinel
        archive = MagicMock()

        result = service.load_image_stack(
            archive=archive,
            metadata=metadata,
            params=params,
            config=config,
            slices_to_load=np.array([0, 1, 2, 3, 4]),
            sel_data_type='Raw',
            progress_callback=None,
        )

        assert result is sentinel
        mock_octF.createImageFromRaw.assert_called_once()

    @pytest.mark.unit
    def test_process_slice_yz_direction_with_resize(self, sample_3d_image_stack, metadata):
        service = ExportService()
        params = SliceExportParams(
            file_path='C:/data/test.oct', name='S',
            first_slice=1, last_slice=10, num_slices=5,
            slice_direction='YZ',
        )
        config = ExportConfig(resize_enabled=True, scale_enabled=False)

        result = service.process_slice(
            img_stack=sample_3d_image_stack,
            slice_idx=0, image_idx=5,
            params=params, config=config, metadata=metadata,
        )
        assert isinstance(result, Image.Image)

    @pytest.mark.unit
    def test_process_slice_xy_direction_with_resize(self, sample_3d_image_stack, metadata):
        service = ExportService()
        params = SliceExportParams(
            file_path='C:/data/test.oct', name='S',
            first_slice=1, last_slice=10, num_slices=5,
            slice_direction='XY',
        )
        config = ExportConfig(resize_enabled=True, scale_enabled=False)

        result = service.process_slice(
            img_stack=sample_3d_image_stack,
            slice_idx=0, image_idx=5,
            params=params, config=config, metadata=metadata,
        )
        assert isinstance(result, Image.Image)

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_export_video_image_success(self, mock_octF, metadata, tmp_path):
        service = ExportService()
        params = SliceExportParams(
            file_path='C:/data/test.oct', name='S',
            first_slice=1, last_slice=10, num_slices=5,
        )
        mock_octF.createVideoImageFromRaw.return_value = np.random.randint(
            0, 256, (32, 32), dtype=np.uint8
        )
        export_dir = tmp_path / "sub"
        export_dir.mkdir()

        result = service.export_video_image(MagicMock(), metadata, params, export_dir)

        assert result is not None
        assert result.exists()

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_export_video_image_failure_returns_none(self, mock_octF, metadata, tmp_path):
        service = ExportService()
        params = SliceExportParams(
            file_path='C:/data/test.oct', name='S',
            first_slice=1, last_slice=10, num_slices=5,
        )
        mock_octF.createVideoImageFromRaw.side_effect = RuntimeError("boom")

        result = service.export_video_image(MagicMock(), metadata, params, tmp_path)

        assert result is None

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_run_export_full_pipeline(self, mock_octF, sample_xml_dict, tmp_path):
        service = ExportService()
        archive = MagicMock()
        mock_octF.unzipOCTData.return_value = archive
        mock_octF.readXMLContent.return_value = '<xml/>'
        mock_octF.getXMLAttributes.return_value = sample_xml_dict
        mock_octF.createImageFromRaw.return_value = np.random.randint(
            0, 256, (2, 64, 64), dtype=np.uint8
        )
        mock_octF.createVideoImageFromRaw.return_value = np.random.randint(
            0, 256, (32, 32), dtype=np.uint8
        )

        oct_file = tmp_path / "scan.oct"
        oct_file.write_bytes(b"dummy")
        params = SliceExportParams(
            file_path=str(oct_file), name='S',
            first_slice=1, last_slice=10, num_slices=2,
            slice_direction='XZ',
        )
        config = ExportConfig(resize_enabled=False, scale_enabled=False)

        progress = []
        result = service.run_export(
            str(oct_file), params, config,
            progress_callback=lambda p: progress.append(p),
        )

        assert len(result.exported_files) == 2
        assert all(Path(p).exists() for p in result.exported_files)
        archive.close.assert_called_once()
        assert len(progress) > 0

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_run_export_load_progress_callback(self, mock_octF, sample_xml_dict, tmp_path):
        service = ExportService()
        mock_octF.unzipOCTData.return_value = MagicMock()
        mock_octF.readXMLContent.return_value = '<xml/>'
        mock_octF.getXMLAttributes.return_value = sample_xml_dict
        mock_octF.createVideoImageFromRaw.return_value = np.zeros((8, 8), dtype=np.uint8)

        def fake_create(*args, **kwargs):
            cb = kwargs.get('update_callback')
            if cb:
                cb("loading 50%")
            return np.random.randint(0, 256, (2, 32, 32), dtype=np.uint8)

        mock_octF.createImageFromRaw.side_effect = fake_create

        oct_file = tmp_path / "scan.oct"
        oct_file.write_bytes(b"dummy")
        params = SliceExportParams(
            file_path=str(oct_file), name='S',
            first_slice=1, last_slice=10, num_slices=2,
        )
        config = ExportConfig(resize_enabled=False, scale_enabled=False)

        statuses = []
        service.run_export(str(oct_file), params, config,
                           progress_callback=lambda p: statuses.append(p.status))

        assert any('Loading' in s for s in statuses)

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_run_export_cancelled_skips_slices(self, mock_octF, sample_xml_dict, tmp_path):
        service = ExportService()
        mock_octF.unzipOCTData.return_value = MagicMock()
        mock_octF.readXMLContent.return_value = '<xml/>'
        mock_octF.getXMLAttributes.return_value = sample_xml_dict
        mock_octF.createVideoImageFromRaw.return_value = np.zeros((8, 8), dtype=np.uint8)

        def fake_create(*args, **kwargs):
            service.cancel()  # cancel before slice loop begins
            return np.random.randint(0, 256, (2, 32, 32), dtype=np.uint8)

        mock_octF.createImageFromRaw.side_effect = fake_create

        oct_file = tmp_path / "scan.oct"
        oct_file.write_bytes(b"dummy")
        params = SliceExportParams(
            file_path=str(oct_file), name='S',
            first_slice=1, last_slice=10, num_slices=2,
        )
        config = ExportConfig(resize_enabled=False, scale_enabled=False)

        result = service.run_export(str(oct_file), params, config)

        assert result.exported_files == []

    @pytest.mark.unit
    @patch('app.logic.rexview.export_service.octF')
    def test_run_export_continues_on_slice_error(self, mock_octF, sample_xml_dict, tmp_path):
        service = ExportService()
        mock_octF.unzipOCTData.return_value = MagicMock()
        mock_octF.readXMLContent.return_value = '<xml/>'
        mock_octF.getXMLAttributes.return_value = sample_xml_dict
        mock_octF.createImageFromRaw.return_value = np.random.randint(
            0, 256, (2, 32, 32), dtype=np.uint8
        )
        mock_octF.createVideoImageFromRaw.return_value = np.zeros((8, 8), dtype=np.uint8)

        oct_file = tmp_path / "scan.oct"
        oct_file.write_bytes(b"dummy")
        params = SliceExportParams(
            file_path=str(oct_file), name='S',
            first_slice=1, last_slice=10, num_slices=2,
        )
        config = ExportConfig(resize_enabled=False, scale_enabled=False)

        with patch.object(service, 'process_slice', side_effect=RuntimeError("bad slice")):
            result = service.run_export(str(oct_file), params, config)

        assert result.exported_files == []


# ============================================================================
# ImageService
# ============================================================================

class TestImageServiceUncovered:
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)

    @pytest.mark.unit
    @patch('app.logic.rexview.image_service.octF')
    def test_load_processed_stack(self, mock_octF, metadata):
        service = ImageService()
        service._archive = MagicMock()
        service._metadata = metadata
        arr = np.zeros((2, 4, 4), dtype=np.uint8)
        mock_octF.createImageFromRaw.return_value = arr

        result = service.load_processed_stack(ImageDisplayConfig(data_type='Processed'))

        assert result is arr
        assert service._image_stack is arr

    @pytest.mark.unit
    def test_load_processed_stack_no_file_raises(self):
        service = ImageService()
        with pytest.raises(ValueError):
            service.load_processed_stack(ImageDisplayConfig())

    @pytest.mark.unit
    @patch('app.logic.rexview.image_service.octF')
    def test_create_raw_slice(self, mock_octF, metadata):
        service = ImageService()
        service._archive = MagicMock()
        service._metadata = metadata
        arr = np.zeros((4, 4), dtype=np.uint8)
        mock_octF.createImageFromRaw.return_value = arr

        result = service.create_raw_slice(ImageDisplayConfig(data_type='Raw'))

        assert result is arr

    @pytest.mark.unit
    def test_create_raw_slice_no_file_raises(self):
        service = ImageService()
        with pytest.raises(ValueError):
            service.create_raw_slice(ImageDisplayConfig())

    @pytest.mark.unit
    def test_apply_resize_correction_unknown_direction_returns_input(self):
        service = ImageService()
        img = np.zeros((4, 4), dtype=np.uint8)
        result = service.apply_resize_correction(img, 'INVALID', 1.0, 1.0)
        assert result is img

    @pytest.mark.unit
    @patch('app.logic.rexview.image_service.octF')
    def test_add_scale_bar(self, mock_octF, metadata):
        service = ImageService()
        service._metadata = metadata
        mock_octF.insertScale.return_value = 'scaled'
        img = Image.fromarray(np.zeros((8, 8), dtype=np.uint8))

        result = service.add_scale_bar(img, 500, 30, 'XZ')

        assert result == 'scaled'
        mock_octF.insertScale.assert_called_once()

    @pytest.mark.unit
    def test_add_scale_bar_no_metadata_raises(self):
        service = ImageService()
        img = Image.fromarray(np.zeros((8, 8), dtype=np.uint8))
        with pytest.raises(ValueError):
            service.add_scale_bar(img, 500, 30, 'XZ')

    @pytest.mark.unit
    @patch('app.logic.rexview.image_service.octF')
    def test_process_preview_image_raw_with_scale(self, mock_octF, metadata):
        service = ImageService()
        service._archive = MagicMock()
        service._metadata = metadata
        raw2d = np.random.randint(0, 256, (64, 64), dtype=np.uint8)
        mock_octF.createImageFromRaw.return_value = raw2d
        mock_octF.insertScale.side_effect = lambda img, **kwargs: img

        config = ImageDisplayConfig(
            data_type='Raw',
            scale_enabled=True,
            resize_enabled=False,
            refractive_index=1.0,
            canvas_width=100,
            canvas_height=50,
        )

        img, x_pos = service.process_preview_image(config)

        assert isinstance(img, Image.Image)
        assert isinstance(x_pos, int)


# ============================================================================
# QueueService
# ============================================================================

def _make_queue_item(**overrides) -> QueueItem:
    """Build a QueueItem bypassing validation so error branches can be tested."""
    base = dict(
        name='f', first_slice=1, last_slice=10, db_min=20, db_max=80,
        num_slices=5, refractive_index=1.0, dispersion_coefficient=20,
        slice_direction='XZ', data_type='Processed', status='in queue',
        file_path='x.oct',
    )
    base.update(overrides)
    return QueueItem.model_construct(**base)


class TestQueueServiceUncovered:
    @pytest.fixture
    def service(self):
        return QueueService()

    @pytest.mark.unit
    def test_validate_item_all_error_branches(self, service):
        item = _make_queue_item(
            first_slice=20, last_slice=10,
            db_min=80, db_max=20,
            slice_direction='AB',
            refractive_index=10.0,
            file_path='',
        )
        result = service.validate_item(item)
        assert result.is_valid is False
        joined = " ".join(result.errors)
        assert 'first_slice' in joined
        assert 'db_min' in joined
        assert 'Invalid slice_direction' in joined
        assert 'refractive_index' in joined
        assert 'file_path' in joined

    @pytest.mark.unit
    def test_update_direction_for_item(self, service):
        item = _make_queue_item()
        result = service.update_direction_for_item(item, 'YZ', 256)
        assert result['slice_direction'] == 'YZ'
        assert result['last_slice'] == 256
        assert result['num_slices'] == 256

    @pytest.mark.unit
    def test_validate_batch_update_empty(self, service):
        result = service.validate_batch_update([], {'db_min': 10})
        assert result.is_valid is True
        assert any('No items' in w for w in result.warnings)

    @pytest.mark.unit
    def test_validate_batch_update_missing_paths(self, service):
        items = [_make_queue_item(file_path=''), _make_queue_item()]
        result = service.validate_batch_update(items, {'db_min': 10})
        assert result.is_valid is True
        assert any('no valid path' in w for w in result.warnings)


# ============================================================================
# SettingsService
# ============================================================================

class TestSettingsServiceUncovered:
    @pytest.fixture
    def service(self):
        return SettingsService()

    def _bad_config(self, service, **overrides) -> SettingsConfig:
        data = service.get_defaults().model_dump()
        data.update(overrides)
        return SettingsConfig.model_construct(**data)

    @pytest.mark.unit
    def test_validate_export_config_db_min_ge_max(self, service):
        cfg = self._bad_config(service, db_min=100, db_max=50)
        result = service.validate_export_config(cfg)
        assert result.is_valid is False
        assert any('db_min' in e for e in result.errors)

    @pytest.mark.unit
    def test_validate_export_config_invalid_scale_font(self, service):
        cfg = self._bad_config(service, scale_enabled=True, scale_font_size=0)
        result = service.validate_export_config(cfg)
        assert any('scale_font_size' in e for e in result.errors)

    @pytest.mark.unit
    def test_validate_export_config_dispersion_out_of_range(self, service):
        cfg = self._bad_config(service, dispersion_type='Quadratic', dispersion_coefficient=200)
        result = service.validate_export_config(cfg)
        assert any('dispersion_coefficient' in e for e in result.errors)

    @pytest.mark.unit
    def test_validate_export_config_advanced_filter_warning(self, service):
        cfg = service.merge_with_defaults({'advanced_filter': True, 'averaging': 'none'})
        result = service.validate_export_config(cfg)
        assert any('Advanced filter' in w for w in result.warnings)

    @pytest.mark.unit
    def test_validate_slice_range_last_slice_below_one(self, service):
        result = service.validate_slice_range(first_slice=1, last_slice=0, total_slices=10)
        assert result.is_valid is False
        assert any('last_slice' in e for e in result.errors)


# ============================================================================
# FileDiscoveryService
# ============================================================================

class TestFileDiscoveryUncovered:
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()

    @pytest.mark.unit
    @patch('app.logic.rexview.file_discovery_service.os.walk', side_effect=PermissionError("denied"))
    def test_scan_directory_permission_error(self, mock_walk, service, tmp_path):
        result = service.scan_directory(tmp_path, recursive=True)
        assert any('Permission denied' in e for e in result.errors)

    @pytest.mark.unit
    @patch('app.logic.rexview.file_discovery_service.os.walk', side_effect=RuntimeError("boom"))
    def test_scan_directory_generic_error(self, mock_walk, service, tmp_path):
        result = service.scan_directory(tmp_path, recursive=True)
        assert any('Error scanning directory' in e for e in result.errors)

    @pytest.mark.unit
    def test_validate_file_path_is_directory(self, service, tmp_path):
        d = tmp_path / "d.oct"
        d.mkdir()
        result = service.validate_file(d)
        assert result.is_valid is False
        assert any('not a file' in e for e in result.errors)

    @pytest.mark.unit
    def test_validate_file_stat_error_adds_warning(self, service, tmp_path):
        oct_file = tmp_path / "scan.oct"
        oct_file.write_bytes(b"x" * 2000)

        real_stat = Path.stat

        def flaky_stat(self, *args, **kwargs):
            # The only explicit Path.stat() call is the size check; make it fail.
            if self.name == "scan.oct":
                raise OSError("cannot stat")
            return real_stat(self, *args, **kwargs)

        with patch.object(Path, 'stat', flaky_stat):
            result = service.validate_file(oct_file)

        assert any('Could not check file size' in w for w in result.warnings)

    @pytest.mark.unit
    def test_parse_metadata_file_two_token_variants(self, service, tmp_path):
        meta = tmp_path / "scan.txt"
        meta.write_text("10-20:5\n30-40:1.5\n")
        result = service.parse_metadata_file(meta)
        assert 'XZ' in result

    @pytest.mark.unit
    def test_parse_metadata_file_invalid_range(self, service, tmp_path):
        meta = tmp_path / "scan.txt"
        meta.write_text("XZ:10-ab:5\n")
        with pytest.raises(ValueError):
            service.parse_metadata_file(meta)

    @pytest.mark.unit
    def test_handle_metadata_parsing_value_error_fallback(self, service, tmp_path):
        meta = tmp_path / "scan.txt"
        meta.write_text("totally-bad-content-no-colons-or-range\n")
        settings, error_msg = service.handle_metadata_parsing(meta, dim_y=128, show_errors=True)
        assert 'XZ' in settings
        assert error_msg is not None
        assert 'parsing' in error_msg.lower()

    @pytest.mark.unit
    def test_handle_metadata_parsing_runtime_error_fallback(self, service, tmp_path):
        meta = tmp_path / "scan.txt"
        meta.write_text("XZ:1-10:5\n")
        with patch.object(service, 'parse_metadata_file', side_effect=RuntimeError("io")):
            settings, error_msg = service.handle_metadata_parsing(meta, dim_y=128, show_errors=True)
        assert 'XZ' in settings
        assert error_msg is not None

    @pytest.mark.unit
    def test_process_file_invalid_returns_error(self, service, tmp_path):
        items, error = service.process_file(tmp_path / "nope.oct")
        assert items == []
        assert error is not None

    @pytest.mark.unit
    def test_process_directory_scan_errors(self, service, tmp_path):
        items, errors = service.process_directory(tmp_path / "missing_dir")
        assert items == []
        assert len(errors) > 0

    @pytest.mark.unit
    def test_process_directory_no_files(self, service, tmp_path):
        items, errors = service.process_directory(tmp_path)
        assert items == []
        assert any('No OCT files' in e for e in errors)

    @pytest.mark.unit
    def test_process_directory_collects_file_errors(self, service, tmp_path):
        # Empty .oct file fails validation -> error collected
        (tmp_path / "empty.oct").write_bytes(b"")
        items, errors = service.process_directory(tmp_path)
        assert items == []
        assert len(errors) > 0

    @pytest.mark.unit
    def test_process_directory_progress_callback_break(self, service, tmp_path):
        (tmp_path / "a.oct").write_bytes(b"")
        (tmp_path / "b.oct").write_bytes(b"")
        calls = []

        def cb(current, total):
            calls.append(current)
            return False  # request stop after first

        service.process_directory(tmp_path, progress_callback=cb)
        assert calls == [1]


# ============================================================================
# Models
# ============================================================================

class TestModelsUncovered:
    @pytest.mark.unit
    def test_settings_config_db_min_equal_max_raises(self):
        with pytest.raises(ValueError):
            SettingsConfig(db_min=50, db_max=50)

    @pytest.mark.unit
    def test_settings_config_from_gui_state_invalid_slices_ignored(self):
        config = settings_config_from_gui_state(
            resize_state='selected',
            prefer_raw_state=('selected',),
            advanced_filter_state='!selected',
            export_format='.tiff',
            averaging='coherent',
            tukey_size='0.9',
            error_state='!selected',
            scale_state=('selected',),
            scale_length='500',
            scale_font_size='30',
            first_slice='abc',
            last_slice='xyz',
        )
        assert config.first_slice is None
        assert config.last_slice is None

    @pytest.mark.unit
    def test_export_settings_start_after_end_raises(self):
        with pytest.raises(ValueError):
            ExportSettings(start=10, end=5, num_equidistant_slices=1)
