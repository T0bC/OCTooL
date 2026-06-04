"""
Unit tests for Pydantic models.

Tests model validation, serialization, and factory methods.
"""
import pytest
from pydantic import ValidationError

from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportProgress
from app.logic.shared.models import OCTMetadata


class TestExportConfig:
    """Tests for ExportConfig model."""
    
    @pytest.mark.unit
    def test_default_values(self):
        """GIVEN no arguments, WHEN ExportConfig is created, THEN defaults are applied."""
        config = ExportConfig()
        
        assert config.resize_enabled is True
        assert config.prefer_raw is True
        assert config.advanced_filter is False
        assert config.export_format == '.tiff'
        assert config.averaging == 'coherent'
        assert config.tukey_window_size == 0.9
        assert config.scale_enabled is True
        assert config.scale_length_um == 500
        assert config.scale_font_size == 30
        assert config.worker_count is None

    @pytest.mark.unit
    def test_worker_count_override(self):
        """GIVEN a worker_count, WHEN ExportConfig is created, THEN it is stored."""
        config = ExportConfig(worker_count=3)
        assert config.worker_count == 3

    @pytest.mark.unit
    def test_worker_count_must_be_positive(self):
        """GIVEN worker_count < 1, WHEN ExportConfig is created, THEN ValidationError."""
        with pytest.raises(ValidationError):
            ExportConfig(worker_count=0)
    
    @pytest.mark.unit
    def test_custom_values(self):
        """GIVEN custom values, WHEN ExportConfig is created, THEN values are set."""
        config = ExportConfig(
            resize_enabled=False,
            prefer_raw=False,
            export_format='.png',
            averaging='incoherent',
            tukey_window_size=0.5,
            scale_length_um=1000,
        )
        
        assert config.resize_enabled is False
        assert config.prefer_raw is False
        assert config.export_format == '.png'
        assert config.averaging == 'incoherent'
        assert config.tukey_window_size == 0.5
        assert config.scale_length_um == 1000
    
    @pytest.mark.unit
    def test_invalid_export_format(self):
        """GIVEN invalid export format, WHEN ExportConfig is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError):
            ExportConfig(export_format='.jpg')
    
    @pytest.mark.unit
    def test_invalid_averaging(self):
        """GIVEN invalid averaging method, WHEN ExportConfig is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError):
            ExportConfig(averaging='invalid')
    
    @pytest.mark.unit
    def test_tukey_window_bounds(self):
        """GIVEN out-of-bounds tukey value, WHEN ExportConfig is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError):
            ExportConfig(tukey_window_size=1.5)
        
        with pytest.raises(ValidationError):
            ExportConfig(tukey_window_size=-0.1)
    
    @pytest.mark.unit
    def test_from_gui_state(self):
        """GIVEN GUI widget states, WHEN from_gui_state is called, THEN config is created correctly."""
        config = ExportConfig.from_gui_state(
            resize_state='selected',
            prefer_raw_state=('selected',),
            advanced_filter_state='',
            export_format='.png',
            averaging='none',
            tukey_size='0.8',
            scale_state=('selected',),
            scale_length='250',
            scale_font_size='24',
        )
        
        assert config.resize_enabled is True
        assert config.prefer_raw is True
        assert config.advanced_filter is False
        assert config.export_format == '.png'
        assert config.averaging == 'none'
        assert config.tukey_window_size == 0.8
        assert config.scale_enabled is True
        assert config.scale_length_um == 250
        assert config.scale_font_size == 24


class TestSliceExportParams:
    """Tests for SliceExportParams model."""
    
    @pytest.mark.unit
    def test_valid_params(self):
        """GIVEN valid parameters, WHEN SliceExportParams is created, THEN no errors occur."""
        params = SliceExportParams(
            file_path='/path/to/file.oct',
            name='TestScan',
            first_slice=1,
            last_slice=100,
            num_slices=10,
            slice_direction='XZ',
            db_min=20,
            db_max=80,
        )
        
        assert params.file_path == '/path/to/file.oct'
        assert params.name == 'TestScan'
        assert params.first_slice == 1
        assert params.last_slice == 100
        assert params.num_slices == 10
    
    @pytest.mark.unit
    def test_invalid_slice_range(self):
        """GIVEN first_slice > last_slice, WHEN SliceExportParams is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError) as exc_info:
            SliceExportParams(
                file_path='/path/to/file.oct',
                name='Test',
                first_slice=50,
                last_slice=10,
                num_slices=5,
            )
        assert 'first_slice' in str(exc_info.value)
    
    @pytest.mark.unit
    def test_num_slices_exceeds_range(self):
        """GIVEN num_slices > available range, WHEN SliceExportParams is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError) as exc_info:
            SliceExportParams(
                file_path='/path/to/file.oct',
                name='Test',
                first_slice=1,
                last_slice=10,
                num_slices=20,  # Only 10 available
            )
        assert 'num_slices' in str(exc_info.value)
    
    @pytest.mark.unit
    def test_invalid_slice_direction(self):
        """GIVEN invalid slice direction, WHEN SliceExportParams is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError):
            SliceExportParams(
                file_path='/path/to/file.oct',
                name='Test',
                first_slice=1,
                last_slice=10,
                num_slices=5,
                slice_direction='ZZ',
            )
    
    @pytest.mark.unit
    def test_refractive_index_bounds(self):
        """GIVEN out-of-bounds refractive index, WHEN SliceExportParams is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError):
            SliceExportParams(
                file_path='/path/to/file.oct',
                name='Test',
                first_slice=1,
                last_slice=10,
                num_slices=5,
                refractive_index=0.05,  # Too low
            )
    
    @pytest.mark.unit
    def test_export_dir_name_property(self):
        """GIVEN valid params, WHEN export_dir_name is accessed, THEN correct name is returned."""
        params = SliceExportParams(
            file_path='/path/to/file.oct',
            name='MyScan',
            first_slice=1,
            last_slice=100,
            num_slices=25,
            slice_direction='YZ',
        )
        
        assert params.export_dir_name == 'MyScan_25_Slices_YZ'
    
    @pytest.mark.unit
    def test_from_treeview_row(self):
        """GIVEN TreeView row values, WHEN from_treeview_row is called, THEN params are created correctly."""
        params = SliceExportParams.from_treeview_row(
            path='C:/data/scan.oct',
            name='Scan001',
            first='5',
            last='50',
            num_slices='10',
            slice_dir='XZ',
            db_min='25',
            db_max='75',
            refr_ind='1.38',
            dispersion=('Quadratic', '100'),
        )
        
        assert params.file_path == 'C:/data/scan.oct'
        assert params.first_slice == 5
        assert params.last_slice == 50
        assert params.num_slices == 10
        assert params.db_min == 25
        assert params.db_max == 75
        assert params.refractive_index == 1.38
        assert params.dispersion == ('Quadratic', '100')


class TestExportProgress:
    """Tests for ExportProgress model."""
    
    @pytest.mark.unit
    def test_default_values(self):
        """GIVEN no arguments, WHEN ExportProgress is created, THEN defaults are applied."""
        progress = ExportProgress()
        
        assert progress.current_item == 0
        assert progress.total_items == 0
        assert progress.current_slice == 0
        assert progress.total_slices == 0
        assert progress.status == 'idle'
    
    @pytest.mark.unit
    def test_item_progress_calculation(self):
        """GIVEN progress values, WHEN item_progress is accessed, THEN correct percentage is returned."""
        progress = ExportProgress(current_item=3, total_items=10)
        assert progress.item_progress == 30.0
    
    @pytest.mark.unit
    def test_slice_progress_calculation(self):
        """GIVEN progress values, WHEN slice_progress is accessed, THEN correct percentage is returned."""
        progress = ExportProgress(current_slice=7, total_slices=20)
        assert progress.slice_progress == 35.0
    
    @pytest.mark.unit
    def test_progress_zero_division(self):
        """GIVEN zero totals, WHEN progress is accessed, THEN returns 0.0."""
        progress = ExportProgress()
        assert progress.item_progress == 0.0
        assert progress.slice_progress == 0.0


class TestOCTMetadata:
    """Tests for OCTMetadata model."""
    
    @pytest.mark.unit
    def test_from_xml_dict(self, sample_xml_dict):
        """GIVEN a valid xmlDict, WHEN from_xml_dict is called, THEN OCTMetadata is created."""
        metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        
        assert metadata.data_type == 'RawSpectraAndProcessedIntensity'
        assert metadata.dim_x == 512
        assert metadata.dim_y == 128
        assert metadata.dim_z == 512
        assert metadata.exp_number == 1
        assert metadata.is_3d is True
    
    @pytest.mark.unit
    def test_to_xml_dict_roundtrip(self, sample_xml_dict):
        """GIVEN OCTMetadata, WHEN to_xml_dict is called, THEN original keys are preserved."""
        metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        result = metadata.to_xml_dict()
        
        # Check key fields are preserved with original names
        assert result['dataType'] == sample_xml_dict['dataType']
        assert result['dimX'] == sample_xml_dict['dimX']
        assert result['expNumber'] == sample_xml_dict['expNumber']
    
    @pytest.mark.unit
    def test_has_raw_data_property(self, sample_xml_dict):
        """GIVEN metadata with raw data, WHEN has_raw_data is accessed, THEN returns True."""
        metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        assert metadata.has_raw_data is True
        
        # Test with processed-only data
        processed_dict = sample_xml_dict.copy()
        processed_dict['dataType'] = 'Processed'
        metadata_processed = OCTMetadata.from_xml_dict(processed_dict)
        assert metadata_processed.has_raw_data is False
    
    @pytest.mark.unit
    def test_has_processed_data_property(self, sample_xml_dict):
        """GIVEN metadata, WHEN has_processed_data is accessed, THEN returns correct value."""
        metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        assert metadata.has_processed_data is True
        
        # Test with raw-only data
        raw_dict = sample_xml_dict.copy()
        raw_dict['dataType'] = 'RawSpectra'
        metadata_raw = OCTMetadata.from_xml_dict(raw_dict)
        assert metadata_raw.has_processed_data is False
    
    @pytest.mark.unit
    def test_validation_errors(self):
        """GIVEN invalid data, WHEN OCTMetadata is created, THEN ValidationError is raised."""
        with pytest.raises(ValidationError):
            OCTMetadata(
                dataType='Test',
                dimX=-1,  # Invalid: must be >= 1
                dimY=100,
                dimZ=100,
                imgSize=(100, 100),
                spacingX=1.0,
                spacingY=1.0,
                spacingZ=1.0,
            )
    
    @pytest.mark.unit
    def test_extra_fields_allowed(self, sample_xml_dict):
        """GIVEN xmlDict with extra fields, WHEN from_xml_dict is called, THEN no error occurs."""
        extended_dict = sample_xml_dict.copy()
        extended_dict['customField'] = 'custom_value'
        extended_dict['anotherField'] = 12345
        
        # Should not raise
        metadata = OCTMetadata.from_xml_dict(extended_dict)
        assert metadata.dim_x == 512
