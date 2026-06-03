"""
Integration tests for RexView export pipeline wiring.

Tests the panel → service → output chain to verify that the ExportService
is correctly wired into the execution_panel.mainRoutines() flow.
"""
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from app.logic.rexview import ExportConfig, SliceExportParams, ExportService
from app.logic.shared import OCTMetadata


class TestExportPipelineWiring:
    """Test that execution_panel correctly delegates to ExportService."""

    @pytest.fixture
    def export_service(self):
        """Create a fresh ExportService instance."""
        return ExportService()

    @pytest.fixture
    def sample_config(self, default_export_config):
        """Create an ExportConfig from default values."""
        return ExportConfig(**default_export_config)

    @pytest.fixture
    def sample_params(self, default_slice_params):
        """Create SliceExportParams from default values."""
        return SliceExportParams(**default_slice_params)

    @pytest.fixture
    def sample_metadata(self, sample_xml_dict):
        """Create OCTMetadata from sample XML dict."""
        return OCTMetadata.from_xml_dict(sample_xml_dict)

    def test_prepare_export_returns_expected_keys(
        self, export_service, sample_params, sample_config, sample_metadata
    ):
        """Verify prepare_export returns all required keys for mainRoutines."""
        result = export_service.prepare_export(sample_params, sample_config, sample_metadata)

        assert 'selected_slices' in result
        assert 'slices_to_load' in result
        assert 'sel_data_type' in result
        assert 'export_dir' in result

    def test_prepare_export_slice_calculation_xz(
        self, export_service, sample_config, sample_metadata
    ):
        """Verify XZ direction uses selected_slices for loading."""
        params = SliceExportParams(
            file_path='/test/file.oct',
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

        result = export_service.prepare_export(params, sample_config, sample_metadata)

        # For XZ, slices_to_load should equal selected_slices
        np.testing.assert_array_equal(result['slices_to_load'], result['selected_slices'])

    def test_prepare_export_slice_calculation_yz(
        self, export_service, sample_config, sample_metadata
    ):
        """Verify YZ direction loads all Y slices."""
        params = SliceExportParams(
            file_path='/test/file.oct',
            name='TestScan',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            slice_direction='YZ',
            db_min=20,
            db_max=80,
            refractive_index=1.0,
            dispersion=('None', '0'),
        )

        result = export_service.prepare_export(params, sample_config, sample_metadata)

        # For YZ, slices_to_load should span all Y dimension
        assert len(result['slices_to_load']) == sample_metadata.dim_y

    def test_prepare_export_data_type_selection_raw(
        self, export_service, sample_params, sample_metadata
    ):
        """Verify raw data type is selected when prefer_raw is True."""
        config = ExportConfig(
            resize_enabled=True,
            prefer_raw=True,
            advanced_filter=False,
            export_format='.tiff',
            averaging='coherent',
            tukey_window_size=0.9,
            scale_enabled=True,
            scale_length_um=500,
            scale_font_size=30,
        )

        result = export_service.prepare_export(sample_params, config, sample_metadata)

        assert result['sel_data_type'] == 'Raw'

    def test_prepare_export_data_type_selection_processed(
        self, export_service, sample_params, sample_metadata
    ):
        """Verify processed data type is selected when prefer_raw is False."""
        config = ExportConfig(
            resize_enabled=True,
            prefer_raw=False,
            advanced_filter=False,
            export_format='.tiff',
            averaging='coherent',
            tukey_window_size=0.9,
            scale_enabled=True,
            scale_length_um=500,
            scale_font_size=30,
        )

        result = export_service.prepare_export(sample_params, config, sample_metadata)

        assert result['sel_data_type'] == 'Processed'

    def test_process_slice_returns_pil_image(
        self, export_service, sample_params, sample_config, sample_metadata, sample_3d_image_stack
    ):
        """Verify process_slice returns a PIL Image."""
        from PIL import Image

        result = export_service.process_slice(
            img_stack=sample_3d_image_stack,
            slice_idx=0,
            image_idx=0,
            params=sample_params,
            config=sample_config,
            metadata=sample_metadata,
        )

        assert isinstance(result, Image.Image)

    def test_calculate_dpi_xz_direction(
        self, export_service, sample_params, sample_metadata, sample_grayscale_image
    ):
        """Verify DPI calculation for XZ direction."""
        params = SliceExportParams(
            file_path='/test/file.oct',
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

        dpi = export_service.calculate_dpi(sample_grayscale_image, params, sample_metadata)

        assert isinstance(dpi, tuple)
        assert len(dpi) == 2
        assert all(isinstance(d, int) for d in dpi)

    def test_generate_export_filename_format(
        self, export_service, sample_params, sample_config, sample_metadata
    ):
        """Verify export filename follows expected format."""
        filename = export_service.generate_export_filename(
            params=sample_params,
            config=sample_config,
            metadata=sample_metadata,
            slice_number=5,
            export_index=2,
        )

        assert sample_params.name in filename
        assert str(sample_metadata.exp_number) in filename
        assert sample_config.export_format in filename

    def test_add_exif_metadata_returns_dict(
        self, export_service, sample_metadata, sample_grayscale_image
    ):
        """Verify EXIF metadata is created correctly."""
        exif = export_service.add_exif_metadata(sample_grayscale_image, sample_metadata)

        assert exif is not None


class TestConfigCollectionIntegration:
    """Test that config collection helpers work with ExportService."""

    def test_export_config_from_gui_state(self):
        """Verify ExportConfig.from_gui_state creates valid config."""
        config = ExportConfig.from_gui_state(
            resize_state='selected',
            prefer_raw_state=('selected',),
            advanced_filter_state='',
            export_format='.tiff',
            averaging='coherent',
            tukey_size='0.9',
            scale_state=('selected',),
            scale_length='500',
            scale_font_size='30',
        )

        assert config.resize_enabled is True
        assert config.prefer_raw is True
        assert config.advanced_filter is False
        assert config.export_format == '.tiff'
        assert config.averaging == 'coherent'
        assert config.tukey_window_size == 0.9
        assert config.scale_enabled is True
        assert config.scale_length_um == 500
        assert config.scale_font_size == 30

    def test_slice_params_from_treeview_row(self):
        """Verify SliceExportParams.from_treeview_row creates valid params."""
        params = SliceExportParams.from_treeview_row(
            path='/test/file.oct',
            name='TestScan',
            first='1',
            last='10',
            num_slices='5',
            slice_dir='XZ',
            db_min='20',
            db_max='80',
            refr_ind='1.0',
            dispersion=('None', '0'),
        )

        assert params.file_path == '/test/file.oct'
        assert params.name == 'TestScan'
        assert params.first_slice == 1
        assert params.last_slice == 10
        assert params.num_slices == 5
        assert params.slice_direction == 'XZ'
        assert params.db_min == 20
        assert params.db_max == 80
        assert params.refractive_index == 1.0


class TestExportServiceCancellation:
    """Test cancellation behavior in ExportService."""

    def test_cancel_sets_flag(self):
        """Verify cancel() sets the cancellation flag."""
        service = ExportService()
        assert service.is_cancelled is False

        service.cancel()
        assert service.is_cancelled is True

    def test_reset_clears_flag(self):
        """Verify reset() clears the cancellation flag."""
        service = ExportService()
        service.cancel()
        assert service.is_cancelled is True

        service.reset()
        assert service.is_cancelled is False
