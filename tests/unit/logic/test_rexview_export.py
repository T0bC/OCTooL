"""
Unit tests for app/logic/rexview/export_service.py

Tests the ExportService business logic without GUI dependencies.
"""
import pytest
import numpy as np
from PIL import Image
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.logic.rexview.export_service import ExportService
from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportProgress
from app.logic.shared.models import OCTMetadata


class TestExportServiceInit:
    """Tests for ExportService initialization and state management."""
    
    @pytest.mark.unit
    def test_init_creates_service(self):
        """GIVEN nothing, WHEN ExportService is created, THEN it initializes correctly."""
        service = ExportService()
        assert service is not None
        assert service.is_cancelled is False
    
    @pytest.mark.unit
    def test_cancel_sets_flag(self):
        """GIVEN a service, WHEN cancel is called, THEN is_cancelled returns True."""
        service = ExportService()
        service.cancel()
        assert service.is_cancelled is True
    
    @pytest.mark.unit
    def test_reset_clears_flag(self):
        """GIVEN a cancelled service, WHEN reset is called, THEN is_cancelled returns False."""
        service = ExportService()
        service.cancel()
        service.reset()
        assert service.is_cancelled is False


class TestPrepareExport:
    """Tests for ExportService.prepare_export method."""
    
    @pytest.fixture
    def service(self):
        return ExportService()
    
    @pytest.fixture
    def params(self):
        return SliceExportParams(
            file_path='C:/data/test.oct',
            name='TestScan',
            first_slice=1,
            last_slice=100,
            num_slices=10,
            slice_direction='XZ',
            db_min=20,
            db_max=80,
        )
    
    @pytest.fixture
    def config(self):
        return ExportConfig()
    
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)
    
    @pytest.mark.unit
    def test_prepare_export_returns_dict(self, service, params, config, metadata):
        """GIVEN valid inputs, WHEN prepare_export is called, THEN returns dict with required keys."""
        result = service.prepare_export(params, config, metadata)
        
        assert isinstance(result, dict)
        assert 'selected_slices' in result
        assert 'slices_to_load' in result
        assert 'sel_data_type' in result
        assert 'export_dir' in result
    
    @pytest.mark.unit
    def test_prepare_export_calculates_slices(self, service, params, config, metadata):
        """GIVEN params with slice range, WHEN prepare_export is called, THEN slices are calculated."""
        result = service.prepare_export(params, config, metadata)
        
        selected = result['selected_slices']
        assert len(selected) == params.num_slices
        assert selected[0] == params.first_slice - 1  # 0-indexed
        assert selected[-1] == params.last_slice - 1
    
    @pytest.mark.unit
    def test_prepare_export_xz_direction(self, service, params, config, metadata):
        """GIVEN XZ slice direction, WHEN prepare_export is called, THEN slices_to_load equals selected."""
        params.slice_direction = 'XZ'
        result = service.prepare_export(params, config, metadata)
        
        np.testing.assert_array_equal(result['slices_to_load'], result['selected_slices'])
    
    @pytest.mark.unit
    def test_prepare_export_yz_direction(self, service, config, metadata):
        """GIVEN YZ slice direction, WHEN prepare_export is called, THEN all Y slices are loaded."""
        params = SliceExportParams(
            file_path='C:/data/test.oct',
            name='TestScan',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            slice_direction='YZ',
        )
        result = service.prepare_export(params, config, metadata)
        
        # For YZ, should load all Y slices
        assert len(result['slices_to_load']) == metadata.dim_y
    
    @pytest.mark.unit
    def test_prepare_export_prefers_raw(self, service, params, config, metadata):
        """GIVEN prefer_raw=True and raw data available, WHEN prepare_export, THEN sel_data_type='Raw'."""
        config.prefer_raw = True
        result = service.prepare_export(params, config, metadata)
        
        assert result['sel_data_type'] == 'Raw'
    
    @pytest.mark.unit
    def test_prepare_export_uses_processed(self, service, params, config, sample_xml_dict):
        """GIVEN prefer_raw=False, WHEN prepare_export is called, THEN sel_data_type='Processed'."""
        config.prefer_raw = False
        sample_xml_dict['dataType'] = 'RawSpectraAndProcessedIntensity'
        metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        
        result = service.prepare_export(params, config, metadata)
        
        assert result['sel_data_type'] == 'Processed'
    
    @pytest.mark.unit
    def test_prepare_export_creates_export_dir(self, service, params, config, metadata):
        """GIVEN valid inputs, WHEN prepare_export is called, THEN export_dir is a Path."""
        result = service.prepare_export(params, config, metadata)
        
        assert isinstance(result['export_dir'], Path)
        assert str(metadata.exp_number) in str(result['export_dir'])


class TestProcessSlice:
    """Tests for ExportService.process_slice method."""
    
    @pytest.fixture
    def service(self):
        return ExportService()
    
    @pytest.fixture
    def params(self):
        return SliceExportParams(
            file_path='C:/data/test.oct',
            name='TestScan',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            slice_direction='XZ',
        )
    
    @pytest.fixture
    def config(self):
        return ExportConfig(resize_enabled=False, scale_enabled=False)
    
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)
    
    @pytest.mark.unit
    def test_process_slice_returns_pil_image(self, service, sample_3d_image_stack, params, config, metadata):
        """GIVEN a 3D image stack, WHEN process_slice is called, THEN returns PIL Image."""
        result = service.process_slice(
            img_stack=sample_3d_image_stack,
            slice_idx=0,
            image_idx=0,
            params=params,
            config=config,
            metadata=metadata,
        )
        
        assert isinstance(result, Image.Image)
    
    @pytest.mark.unit
    def test_process_slice_2d_input(self, service, sample_image_array, params, config, metadata):
        """GIVEN a 2D image array, WHEN process_slice is called, THEN returns PIL Image."""
        result = service.process_slice(
            img_stack=sample_image_array,
            slice_idx=0,
            image_idx=0,
            params=params,
            config=config,
            metadata=metadata,
        )
        
        assert isinstance(result, Image.Image)
    
    @pytest.mark.unit
    def test_process_slice_applies_refractive_index(self, service, sample_3d_image_stack, config, metadata):
        """GIVEN refractive_index != 1, WHEN process_slice is called, THEN image height changes."""
        params_no_refr = SliceExportParams(
            file_path='C:/data/test.oct',
            name='Test',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            refractive_index=1.0,
        )
        params_with_refr = SliceExportParams(
            file_path='C:/data/test.oct',
            name='Test',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            refractive_index=1.5,
        )
        
        result_no_refr = service.process_slice(
            sample_3d_image_stack, 0, 0, params_no_refr, config, metadata
        )
        result_with_refr = service.process_slice(
            sample_3d_image_stack, 0, 0, params_with_refr, config, metadata
        )
        
        # Height should be scaled by refractive index
        assert result_with_refr.size[1] > result_no_refr.size[1]


class TestCalculateDpi:
    """Tests for ExportService.calculate_dpi method."""
    
    @pytest.fixture
    def service(self):
        return ExportService()
    
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)
    
    @pytest.mark.unit
    def test_calculate_dpi_xz(self, service, sample_grayscale_image, metadata):
        """GIVEN XZ slice direction, WHEN calculate_dpi is called, THEN uses X and Z dimensions."""
        params = SliceExportParams(
            file_path='test.oct',
            name='Test',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            slice_direction='XZ',
        )
        
        dpi = service.calculate_dpi(sample_grayscale_image, params, metadata)
        
        assert isinstance(dpi, tuple)
        assert len(dpi) == 2
        assert all(isinstance(d, int) for d in dpi)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("direction", ['XZ', 'YZ', 'XY'])
    def test_calculate_dpi_all_directions(self, service, sample_grayscale_image, metadata, direction):
        """GIVEN any slice direction, WHEN calculate_dpi is called, THEN returns valid DPI tuple."""
        params = SliceExportParams(
            file_path='test.oct',
            name='Test',
            first_slice=1,
            last_slice=10,
            num_slices=5,
            slice_direction=direction,
        )
        
        dpi = service.calculate_dpi(sample_grayscale_image, params, metadata)
        
        assert isinstance(dpi, tuple)
        assert len(dpi) == 2


class TestGenerateExportFilename:
    """Tests for ExportService.generate_export_filename method."""
    
    @pytest.fixture
    def service(self):
        return ExportService()
    
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)
    
    @pytest.mark.unit
    def test_generate_filename_format(self, service, metadata):
        """GIVEN export params, WHEN generate_export_filename is called, THEN filename has correct format."""
        params = SliceExportParams(
            file_path='test.oct',
            name='MyScan',
            first_slice=1,
            last_slice=10,
            num_slices=5,
        )
        config = ExportConfig(export_format='.tiff')
        
        filename = service.generate_export_filename(params, config, metadata, slice_number=5, export_index=2)
        
        assert 'MyScan' in filename
        assert str(metadata.exp_number) in filename
        assert '#6' in filename  # slice_number + 1
        assert '0003' in filename  # export_index + 1, zero-padded
        assert filename.endswith('.tiff')
    
    @pytest.mark.unit
    def test_generate_filename_png_format(self, service, metadata):
        """GIVEN export_format='.png', WHEN generate_export_filename is called, THEN filename ends with .png."""
        params = SliceExportParams(
            file_path='test.oct',
            name='Test',
            first_slice=1,
            last_slice=10,
            num_slices=5,
        )
        config = ExportConfig(export_format='.png')
        
        filename = service.generate_export_filename(params, config, metadata, 0, 0)
        
        assert filename.endswith('.png')


class TestAddExifMetadata:
    """Tests for ExportService.add_exif_metadata method."""
    
    @pytest.fixture
    def service(self):
        return ExportService()
    
    @pytest.fixture
    def metadata(self, sample_xml_dict):
        return OCTMetadata.from_xml_dict(sample_xml_dict)
    
    @pytest.mark.unit
    def test_add_exif_returns_dict(self, service, sample_grayscale_image, metadata):
        """GIVEN an image and metadata, WHEN add_exif_metadata is called, THEN returns exif dict."""
        exif = service.add_exif_metadata(sample_grayscale_image, metadata)
        
        assert exif is not None
        # EXIF should contain user comment with study name
        assert 0x9286 in exif


class TestRunExportPerformance:
    """Step 1 performance guarantees for ExportService.run_export."""

    @pytest.fixture
    def service(self):
        return ExportService()

    @pytest.fixture
    def params(self, tmp_path):
        return SliceExportParams(
            file_path=str(tmp_path / 'scan.oct'),
            name='TestScan',
            first_slice=1,
            last_slice=3,
            num_slices=3,
            slice_direction='XZ',
            db_min=20,
            db_max=80,
            refractive_index=1.0,
            dispersion=('None', '0'),
        )

    @pytest.fixture
    def config(self):
        # scale enabled so process_slice would historically rebuild the dict
        return ExportConfig(resize_enabled=False, scale_enabled=True)

    def _patch_pipeline(self, sample_xml_dict):
        """Patch the heavy octF entry points used by run_export.

        Returns a context-manager-friendly tuple of patchers the caller starts.
        """
        stack = np.zeros((3, 8, 8), dtype=np.uint8)
        patchers = [
            patch('app.logic.rexview.export_service.octF.unzipOCTData', return_value=MagicMock()),
            patch('app.logic.rexview.export_service.octF.readXMLContent', return_value=MagicMock()),
            patch('app.logic.rexview.export_service.octF.getXMLAttributes', return_value=sample_xml_dict),
            patch('app.logic.rexview.export_service.octF.createImageFromRaw', return_value=stack),
            patch('app.logic.rexview.export_service.octF.insertScale', side_effect=lambda **kw: kw['img']),
            patch('app.logic.rexview.export_service.octF.createVideoImageFromRaw',
                  return_value=np.zeros((4, 4, 3), dtype=np.uint8)),
        ]
        return patchers

    @pytest.mark.unit
    def test_run_export_does_not_gc_per_slice(self, service, params, config, sample_xml_dict):
        """GIVEN a multi-slice export, WHEN run_export runs, THEN gc.collect runs at most once."""
        patchers = self._patch_pipeline(sample_xml_dict)
        with patch('app.logic.rexview.export_service.gc') as mock_gc:
            for p in patchers:
                p.start()
            try:
                service.run_export(params.file_path, params, config)
            finally:
                for p in patchers:
                    p.stop()

        assert mock_gc.collect.call_count <= 1

    @pytest.mark.unit
    def test_run_export_returns_export_result(self, service, params, config, sample_xml_dict):
        """GIVEN a successful export, WHEN run_export runs, THEN it returns an ExportResult."""
        from app.logic.rexview.models import ExportResult

        patchers = self._patch_pipeline(sample_xml_dict)
        for p in patchers:
            p.start()
        try:
            result = service.run_export(params.file_path, params, config)
        finally:
            for p in patchers:
                p.stop()

        assert isinstance(result, ExportResult)
        assert result.file_path == params.file_path
        assert all(isinstance(f, str) for f in result.exported_files)
        assert len(result.exported_files) == params.num_slices
        assert result.failed_count == 0
        assert result.error is None

    @pytest.mark.unit
    def test_run_export_builds_xml_dict_once(self, service, params, config, sample_xml_dict):
        """GIVEN a multi-slice export, WHEN run_export runs, THEN to_xml_dict is built once."""
        from app.logic.shared.models import OCTMetadata as _Meta

        real_meta = _Meta.from_xml_dict(sample_xml_dict)
        spy = Mock(side_effect=real_meta.to_xml_dict)

        patchers = self._patch_pipeline(sample_xml_dict)
        meta_patch = patch(
            'app.logic.rexview.export_service.OCTMetadata.from_xml_dict',
            return_value=real_meta,
        )
        with patch.object(real_meta, 'to_xml_dict', spy):
            meta_patch.start()
            for p in patchers:
                p.start()
            try:
                service.run_export(params.file_path, params, config)
            finally:
                for p in patchers:
                    p.stop()
                meta_patch.stop()

        assert spy.call_count == 1


class TestExportSingleSlice:
    """Tests for ExportService.export_single_slice method."""
    
    @pytest.fixture
    def service(self):
        return ExportService()
    
    @pytest.mark.unit
    def test_export_single_slice_creates_file(self, service, sample_grayscale_image, tmp_path):
        """GIVEN an image and path, WHEN export_single_slice is called, THEN file is created."""
        export_path = tmp_path / "test_export.tiff"
        exif = sample_grayscale_image.getexif()
        
        service.export_single_slice(
            image=sample_grayscale_image,
            export_path=export_path,
            dpi=(72, 72),
            exif=exif,
        )
        
        assert export_path.exists()
    
    @pytest.mark.unit
    def test_export_single_slice_converts_to_grayscale(self, service, tmp_path):
        """GIVEN an RGB image, WHEN export_single_slice is called, THEN converts to grayscale."""
        # Create RGB image
        rgb_array = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        rgb_image = Image.fromarray(rgb_array, mode='RGB')
        export_path = tmp_path / "test_rgb.tiff"
        exif = rgb_image.getexif()
        
        service.export_single_slice(rgb_image, export_path, (72, 72), exif)
        
        # Verify saved image is grayscale
        saved_image = Image.open(export_path)
        assert saved_image.mode == 'L'
