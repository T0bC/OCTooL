"""
Unit tests for app/logic/rexview/file_discovery_service.py

Tests the FileDiscoveryService business logic without GUI dependencies.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import os

from app.logic.rexview.file_discovery_service import (
    FileDiscoveryService,
    ValidationResult,
    DiscoveryResult,
)
from app.logic.rexview.models import QueueItem, FileMetadata, ExportSettings


class TestFileDiscoveryServiceInit:
    """Tests for FileDiscoveryService initialization."""
    
    @pytest.mark.unit
    def test_init_creates_service(self):
        """GIVEN nothing, WHEN FileDiscoveryService is created, THEN it initializes correctly."""
        service = FileDiscoveryService()
        assert service is not None
    
    @pytest.mark.unit
    def test_init_with_xml_reader(self):
        """GIVEN xml_reader, WHEN FileDiscoveryService is created, THEN stores reader."""
        mock_reader = Mock(return_value='test')
        service = FileDiscoveryService(xml_reader=mock_reader)
        assert service._xml_reader is mock_reader
    
    @pytest.mark.unit
    def test_default_db_values_exist(self):
        """GIVEN service, WHEN accessing DEFAULT_DB_VALUES, THEN contains expected keys."""
        service = FileDiscoveryService()
        assert 'Processed' in service.DEFAULT_DB_VALUES
        assert 'Raw' in service.DEFAULT_DB_VALUES
    
    @pytest.mark.unit
    def test_oct_pattern(self):
        """GIVEN service, WHEN accessing OCT_PATTERN, THEN is *.oct."""
        service = FileDiscoveryService()
        assert service.OCT_PATTERN == '*.oct'


class TestScanDirectory:
    """Tests for FileDiscoveryService.scan_directory method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.fixture
    def temp_dir_with_oct_files(self):
        """Create a temporary directory with OCT files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create OCT files
            (Path(tmpdir) / "file1.oct").touch()
            (Path(tmpdir) / "file2.oct").touch()
            # Create non-OCT file
            (Path(tmpdir) / "file3.txt").touch()
            # Create subdirectory with OCT file
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            (subdir / "file4.oct").touch()
            yield tmpdir
    
    @pytest.mark.unit
    def test_scan_returns_discovery_result(self, service, temp_dir_with_oct_files):
        """GIVEN directory, WHEN scan_directory, THEN returns DiscoveryResult."""
        result = service.scan_directory(Path(temp_dir_with_oct_files))
        assert isinstance(result, DiscoveryResult)
        assert hasattr(result, 'files')
        assert hasattr(result, 'total_found')
        assert hasattr(result, 'errors')
    
    @pytest.mark.unit
    def test_scan_finds_oct_files_recursive(self, service, temp_dir_with_oct_files):
        """GIVEN directory with OCT files, WHEN scan recursive, THEN finds all OCT files."""
        result = service.scan_directory(Path(temp_dir_with_oct_files), recursive=True)
        assert result.total_found == 3
        assert len(result.errors) == 0
    
    @pytest.mark.unit
    def test_scan_non_recursive(self, service, temp_dir_with_oct_files):
        """GIVEN directory with OCT files, WHEN scan non-recursive, THEN finds only top-level."""
        result = service.scan_directory(Path(temp_dir_with_oct_files), recursive=False)
        assert result.total_found == 2
    
    @pytest.mark.unit
    def test_scan_nonexistent_directory(self, service):
        """GIVEN nonexistent directory, WHEN scan_directory, THEN returns error."""
        result = service.scan_directory(Path("/nonexistent/path"))
        assert result.total_found == 0
        assert len(result.errors) > 0
        assert 'does not exist' in result.errors[0]
    
    @pytest.mark.unit
    def test_scan_file_instead_of_directory(self, service, temp_dir_with_oct_files):
        """GIVEN file path, WHEN scan_directory, THEN returns error."""
        file_path = Path(temp_dir_with_oct_files) / "file1.oct"
        result = service.scan_directory(file_path)
        assert result.total_found == 0
        assert len(result.errors) > 0
        assert 'not a directory' in result.errors[0]
    
    @pytest.mark.unit
    def test_scan_empty_directory(self, service):
        """GIVEN empty directory, WHEN scan_directory, THEN returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = service.scan_directory(Path(tmpdir))
            assert result.total_found == 0
            assert len(result.errors) == 0


class TestValidateFile:
    """Tests for FileDiscoveryService.validate_file method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.mark.unit
    def test_validate_valid_oct_file(self, service):
        """GIVEN valid OCT file, WHEN validate_file, THEN is_valid."""
        # Create temp file, close it, then test (Windows compatibility)
        fd, path = tempfile.mkstemp(suffix='.oct')
        try:
            os.write(fd, b'x' * 10000)
            os.close(fd)
            result = service.validate_file(Path(path))
            assert result.is_valid is True
            assert len(result.errors) == 0
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_validate_nonexistent_file(self, service):
        """GIVEN nonexistent file, WHEN validate_file, THEN error."""
        result = service.validate_file(Path("/nonexistent/file.oct"))
        assert result.is_valid is False
        assert any('does not exist' in e for e in result.errors)
    
    @pytest.mark.unit
    def test_validate_wrong_extension(self, service):
        """GIVEN file with wrong extension, WHEN validate_file, THEN error."""
        fd, path = tempfile.mkstemp(suffix='.txt')
        try:
            os.close(fd)
            result = service.validate_file(Path(path))
            assert result.is_valid is False
            assert any('.oct' in e for e in result.errors)
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_validate_empty_file_warning(self, service):
        """GIVEN empty OCT file, WHEN validate_file, THEN error about empty."""
        fd, path = tempfile.mkstemp(suffix='.oct')
        try:
            os.close(fd)  # Empty file
            result = service.validate_file(Path(path))
            assert result.is_valid is False
            assert any('empty' in e for e in result.errors)
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_validate_small_file_warning(self, service):
        """GIVEN very small OCT file, WHEN validate_file, THEN warning."""
        fd, path = tempfile.mkstemp(suffix='.oct')
        try:
            os.write(fd, b'x' * 100)  # Small file
            os.close(fd)
            result = service.validate_file(Path(path))
            assert result.is_valid is True
            assert any('small' in w for w in result.warnings)
        finally:
            os.unlink(path)


class TestExtractMetadata:
    """Tests for FileDiscoveryService.extract_metadata method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.fixture
    def service_with_reader(self):
        mock_reader = Mock(side_effect=lambda path, key: {
            'dataType': 'Processed',
            'Serialnumber': 'ABC123',
            'dimX': '512',
            'dimY': '256',
            'dimZ': '128',
        }.get(key, ''))
        return FileDiscoveryService(xml_reader=mock_reader)
    
    @pytest.mark.unit
    def test_extract_with_explicit_values(self, service):
        """GIVEN explicit values, WHEN extract_metadata, THEN uses those values."""
        result = service.extract_metadata(
            Path("/path/to/test_file.oct"),
            data_type='Raw',
            serial_number='XYZ789',
            dim_x=1024,
            dim_y=512,
            dim_z=256,
        )
        assert isinstance(result, FileMetadata)
        assert result.file_name == 'test_file'
        assert result.data_type == 'Raw'
        assert result.serial_number == 'XYZ789'
        assert result.dim_x == 1024
    
    @pytest.mark.unit
    def test_extract_with_xml_reader(self, service_with_reader):
        """GIVEN xml_reader, WHEN extract_metadata, THEN uses reader values."""
        result = service_with_reader.extract_metadata(Path("/path/to/file.oct"))
        assert result.data_type == 'Processed'
        assert result.serial_number == 'ABC123'
        assert result.dim_x == 512
        assert result.dim_y == 256
    
    @pytest.mark.unit
    def test_extract_file_name_from_path(self, service):
        """GIVEN path, WHEN extract_metadata, THEN extracts file name without extension."""
        result = service.extract_metadata(
            Path("/some/path/my_oct_scan.oct"),
            data_type='Processed',
        )
        assert result.file_name == 'my_oct_scan'


class TestGetDefaultDbValues:
    """Tests for FileDiscoveryService.get_default_db_values method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.mark.unit
    def test_processed_defaults(self, service):
        """GIVEN 'Processed', WHEN get_default_db_values, THEN returns 20/80."""
        result = service.get_default_db_values('Processed')
        assert result['min'] == 20
        assert result['max'] == 80
    
    @pytest.mark.unit
    def test_raw_defaults(self, service):
        """GIVEN 'Raw', WHEN get_default_db_values, THEN returns 30/100."""
        result = service.get_default_db_values('Raw')
        assert result['min'] == 30
        assert result['max'] == 100
    
    @pytest.mark.unit
    def test_unknown_type_defaults_to_raw(self, service):
        """GIVEN unknown type, WHEN get_default_db_values, THEN returns Raw defaults."""
        result = service.get_default_db_values('UnknownType')
        assert result['min'] == 30
        assert result['max'] == 100


class TestGetDispersionCoefficient:
    """Tests for FileDiscoveryService.get_dispersion_coefficient method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.mark.unit
    def test_special_serial_number(self, service):
        """GIVEN special serial M00427924, WHEN get_dispersion, THEN returns -100."""
        result = service.get_dispersion_coefficient('M00427924')
        assert result == -100
    
    @pytest.mark.unit
    def test_normal_serial_number(self, service):
        """GIVEN normal serial, WHEN get_dispersion, THEN returns default 20."""
        result = service.get_dispersion_coefficient('ABC123')
        assert result == 20
    
    @pytest.mark.unit
    def test_none_serial_number(self, service):
        """GIVEN None serial, WHEN get_dispersion, THEN returns default 20."""
        result = service.get_dispersion_coefficient(None)
        assert result == 20


class TestParseMetadataFile:
    """Tests for FileDiscoveryService.parse_metadata_file method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    def _write_temp_file(self, content: str, suffix: str = '.txt') -> str:
        """Helper to create temp file with content (Windows compatible)."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.write(fd, content.encode('utf-8'))
        os.close(fd)
        return path
    
    @pytest.mark.unit
    def test_parse_simple_range(self, service):
        """GIVEN file with simple range, WHEN parse, THEN extracts correctly with inclusive default count."""
        path = self._write_temp_file("10-50\n")
        try:
            result = service.parse_metadata_file(Path(path))
            assert 'XZ' in result
            assert result['XZ'].start == 10
            assert result['XZ'].end == 50
            assert result['XZ'].num_equidistant_slices == 41
        finally:
            os.unlink(path)

    @pytest.mark.unit
    def test_parse_default_count_is_inclusive(self, service):
        """GIVEN range without explicit count, WHEN parse, THEN defaults to end - start + 1."""
        path = self._write_temp_file("1-100\n")
        try:
            result = service.parse_metadata_file(Path(path))
            assert result['XZ'].num_equidistant_slices == 100
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_parse_with_view_and_count(self, service):
        """GIVEN file with view:range:count, WHEN parse, THEN extracts all."""
        path = self._write_temp_file("YZ:20-80:15\n")
        try:
            result = service.parse_metadata_file(Path(path))
            assert 'YZ' in result
            assert result['YZ'].start == 20
            assert result['YZ'].end == 80
            assert result['YZ'].num_equidistant_slices == 15
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_parse_full_format(self, service):
        """GIVEN file with view:range:count:ri, WHEN parse, THEN extracts all."""
        path = self._write_temp_file("XY:25-90:30:1.33\n")
        try:
            result = service.parse_metadata_file(Path(path))
            assert 'XY' in result
            assert result['XY'].start == 25
            assert result['XY'].end == 90
            assert result['XY'].num_equidistant_slices == 30
            assert result['XY'].refractive_index == 1.33
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_parse_multiple_lines(self, service):
        """GIVEN file with multiple directions, WHEN parse, THEN extracts all."""
        path = self._write_temp_file("XZ:10-100:25:1.0\nYZ:20-80:15:1.0\n")
        try:
            result = service.parse_metadata_file(Path(path))
            assert len(result) == 2
            assert 'XZ' in result
            assert 'YZ' in result
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_parse_skips_comments(self, service):
        """GIVEN file with comments, WHEN parse, THEN skips comments."""
        path = self._write_temp_file("# This is a comment\n10-50\n# Another comment\n")
        try:
            result = service.parse_metadata_file(Path(path))
            assert len(result) == 1
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_parse_invalid_format_raises(self, service):
        """GIVEN file with invalid format, WHEN parse, THEN raises ValueError."""
        path = self._write_temp_file("invalid:format:here:too:many:tokens\n")
        try:
            with pytest.raises(ValueError):
                service.parse_metadata_file(Path(path))
        finally:
            os.unlink(path)
    
    @pytest.mark.unit
    def test_parse_nonexistent_file_raises(self, service):
        """GIVEN nonexistent file, WHEN parse, THEN raises RuntimeError."""
        with pytest.raises(RuntimeError):
            service.parse_metadata_file(Path("/nonexistent/file.txt"))


class TestGetSidecarPath:
    """Tests for FileDiscoveryService.get_sidecar_path method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.mark.unit
    def test_sidecar_path_same_directory(self, service):
        """GIVEN OCT path, WHEN get_sidecar_path, THEN returns .txt in same dir."""
        result = service.get_sidecar_path(Path("/path/to/scan.oct"))
        assert result == Path("/path/to/scan.txt")
    
    @pytest.mark.unit
    def test_sidecar_path_preserves_name(self, service):
        """GIVEN OCT path with complex name, WHEN get_sidecar_path, THEN preserves name."""
        result = service.get_sidecar_path(Path("/data/my_complex_scan_001.oct"))
        assert result.name == "my_complex_scan_001.txt"


class TestGetDefaultExportSettings:
    """Tests for FileDiscoveryService.get_default_export_settings method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.mark.unit
    def test_default_settings_xz_only(self, service):
        """GIVEN dim_y, WHEN get_default_export_settings, THEN returns XZ settings."""
        result = service.get_default_export_settings(256)
        assert 'XZ' in result
        assert len(result) == 1
    
    @pytest.mark.unit
    def test_default_settings_range(self, service):
        """GIVEN dim_y=100, WHEN get_default, THEN range is 1-100."""
        result = service.get_default_export_settings(100)
        assert result['XZ'].start == 1
        assert result['XZ'].end == 100
        assert result['XZ'].num_equidistant_slices == 100
    
    @pytest.mark.unit
    def test_default_settings_refractive_index(self, service):
        """GIVEN dim_y, WHEN get_default, THEN refractive_index is 1.0."""
        result = service.get_default_export_settings(100)
        assert result['XZ'].refractive_index == 1.0


class TestHandleMetadataParsing:
    """Tests for FileDiscoveryService.handle_metadata_parsing method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    def _write_temp_file(self, content: str, suffix: str = '.txt') -> str:
        """Helper to create temp file with content (Windows compatible)."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.write(fd, content.encode('utf-8'))
        os.close(fd)
        return path
    
    @pytest.mark.unit
    def test_handle_nonexistent_file_returns_defaults(self, service):
        """GIVEN nonexistent sidecar, WHEN handle_metadata_parsing, THEN returns defaults."""
        settings, error = service.handle_metadata_parsing(
            Path("/nonexistent/file.txt"),
            dim_y=100,
            show_errors=False,
        )
        assert 'XZ' in settings
        assert settings['XZ'].end == 100
        assert error is None
    
    @pytest.mark.unit
    def test_handle_nonexistent_with_show_errors(self, service):
        """GIVEN nonexistent sidecar with show_errors, WHEN handle, THEN returns error msg."""
        settings, error = service.handle_metadata_parsing(
            Path("/nonexistent/file.txt"),
            dim_y=100,
            show_errors=True,
        )
        assert error is not None
        assert 'No metadata file found' in error
    
    @pytest.mark.unit
    def test_handle_valid_file(self, service):
        """GIVEN valid sidecar, WHEN handle_metadata_parsing, THEN returns parsed settings."""
        path = self._write_temp_file("XZ:10-50:20:1.0\n")
        try:
            settings, error = service.handle_metadata_parsing(
                Path(path),
                dim_y=100,
                show_errors=False,
            )
            assert settings['XZ'].start == 10
            assert settings['XZ'].end == 50
            assert error is None
        finally:
            os.unlink(path)


class TestBuildQueueItemsForFile:
    """Tests for FileDiscoveryService.build_queue_items_for_file method."""
    
    @pytest.fixture
    def service(self):
        return FileDiscoveryService()
    
    @pytest.fixture
    def sample_metadata(self):
        return FileMetadata(
            file_path="/path/to/scan.oct",
            file_name="scan",
            data_type="Processed",
            serial_number="ABC123",
            dim_x=512,
            dim_y=256,
            dim_z=128,
        )
    
    @pytest.fixture
    def sample_settings(self):
        return {
            'XZ': ExportSettings(start=1, end=100, num_equidistant_slices=25, refractive_index=1.0),
        }
    
    @pytest.mark.unit
    def test_build_returns_queue_items(self, service, sample_metadata, sample_settings):
        """GIVEN metadata and settings, WHEN build_queue_items, THEN returns QueueItem list."""
        result = service.build_queue_items_for_file(
            Path("/path/to/scan.oct"),
            sample_metadata,
            sample_settings,
        )
        assert len(result) == 1
        assert isinstance(result[0], QueueItem)
    
    @pytest.mark.unit
    def test_build_sets_correct_values(self, service, sample_metadata, sample_settings):
        """GIVEN metadata and settings, WHEN build, THEN sets correct values."""
        result = service.build_queue_items_for_file(
            Path("/path/to/scan.oct"),
            sample_metadata,
            sample_settings,
        )
        item = result[0]
        assert item.name == "scan"
        assert item.first_slice == 1
        assert item.last_slice == 100
        assert item.num_slices == 25
        assert item.slice_direction == 'XZ'
        assert item.status == 'in queue'
    
    @pytest.mark.unit
    def test_build_multiple_directions(self, service, sample_metadata):
        """GIVEN multiple directions, WHEN build, THEN returns multiple items."""
        settings = {
            'XZ': ExportSettings(start=1, end=100, num_equidistant_slices=25, refractive_index=1.0),
            'YZ': ExportSettings(start=1, end=50, num_equidistant_slices=10, refractive_index=1.0),
        }
        result = service.build_queue_items_for_file(
            Path("/path/to/scan.oct"),
            sample_metadata,
            settings,
        )
        assert len(result) == 2
        directions = {item.slice_direction for item in result}
        assert directions == {'XZ', 'YZ'}
    
    @pytest.mark.unit
    def test_build_uses_correct_db_values(self, service):
        """GIVEN Raw data type, WHEN build, THEN uses Raw dB defaults."""
        metadata = FileMetadata(
            file_path="/path/to/scan.oct",
            file_name="scan",
            data_type="Raw",
            dim_x=512,
            dim_y=256,
            dim_z=128,
        )
        settings = {
            'XZ': ExportSettings(start=1, end=100, num_equidistant_slices=25, refractive_index=1.0),
        }
        result = service.build_queue_items_for_file(
            Path("/path/to/scan.oct"),
            metadata,
            settings,
        )
        assert result[0].db_min == 30
        assert result[0].db_max == 100
    
    @pytest.mark.unit
    def test_build_uses_special_dispersion(self, service):
        """GIVEN special serial number, WHEN build, THEN uses special dispersion."""
        metadata = FileMetadata(
            file_path="/path/to/scan.oct",
            file_name="scan",
            data_type="Processed",
            serial_number="M00427924",
            dim_x=512,
            dim_y=256,
            dim_z=128,
        )
        settings = {
            'XZ': ExportSettings(start=1, end=100, num_equidistant_slices=25, refractive_index=1.0),
        }
        result = service.build_queue_items_for_file(
            Path("/path/to/scan.oct"),
            metadata,
            settings,
        )
        assert result[0].dispersion_coefficient == -100


class TestProcessDirectory:
    """Tests for FileDiscoveryService.process_directory method."""
    
    @pytest.fixture
    def service(self):
        # Use a mock xml_reader that returns sensible defaults
        mock_reader = Mock(side_effect=lambda path, key: {
            'dataType': 'Processed',
            'Serialnumber': 'ABC123',
            'dimX': '512',
            'dimY': '256',
            'dimZ': '128',
        }.get(key, '1'))
        return FileDiscoveryService(xml_reader=mock_reader)
    
    @pytest.mark.unit
    def test_process_nonexistent_directory(self, service):
        """GIVEN nonexistent directory, WHEN process_directory, THEN returns errors."""
        items, errors = service.process_directory(Path("/nonexistent/path"))
        assert len(items) == 0
        assert len(errors) > 0
    
    @pytest.mark.unit
    def test_process_empty_directory(self, service):
        """GIVEN empty directory, WHEN process_directory, THEN returns no files error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            items, errors = service.process_directory(Path(tmpdir))
            assert len(items) == 0
            assert any('No OCT files' in e for e in errors)
    
    @pytest.mark.unit
    def test_process_with_progress_callback(self, service):
        """GIVEN directory with files, WHEN process with callback, THEN callback called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create OCT files with some content
            for i in range(3):
                oct_file = Path(tmpdir) / f"file_{i}.oct"
                oct_file.write_bytes(b'x' * 10000)
            
            progress_calls = []
            def callback(current, total):
                progress_calls.append((current, total))
                return True  # Continue processing
            
            items, errors = service.process_directory(
                Path(tmpdir),
                progress_callback=callback,
            )
            
            assert len(progress_calls) == 3
            assert progress_calls[-1] == (3, 3)
    
    @pytest.mark.unit
    def test_process_cancelled_by_callback(self, service):
        """GIVEN directory with files, WHEN callback returns False, THEN stops early."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create OCT files
            for i in range(5):
                oct_file = Path(tmpdir) / f"file_{i}.oct"
                oct_file.write_bytes(b'x' * 10000)
            
            def callback(current, total):
                return current < 2  # Stop after 2 files
            
            items, errors = service.process_directory(
                Path(tmpdir),
                progress_callback=callback,
            )
            
            # Should have processed only 2 files (1 item each with default XZ direction)
            assert len(items) <= 2


class TestFileMetadataModel:
    """Tests for FileMetadata model methods."""
    
    @pytest.mark.unit
    def test_get_dimension_for_xz(self):
        """GIVEN FileMetadata, WHEN get_dimension_for_direction('XZ'), THEN returns dim_y."""
        metadata = FileMetadata(
            file_path="/path/file.oct",
            file_name="file",
            data_type="Processed",
            dim_x=512,
            dim_y=256,
            dim_z=128,
        )
        assert metadata.get_dimension_for_direction('XZ') == 256
    
    @pytest.mark.unit
    def test_get_dimension_for_yz(self):
        """GIVEN FileMetadata, WHEN get_dimension_for_direction('YZ'), THEN returns dim_x."""
        metadata = FileMetadata(
            file_path="/path/file.oct",
            file_name="file",
            data_type="Processed",
            dim_x=512,
            dim_y=256,
            dim_z=128,
        )
        assert metadata.get_dimension_for_direction('YZ') == 512
    
    @pytest.mark.unit
    def test_get_dimension_for_xy(self):
        """GIVEN FileMetadata, WHEN get_dimension_for_direction('XY'), THEN returns dim_z."""
        metadata = FileMetadata(
            file_path="/path/file.oct",
            file_name="file",
            data_type="Processed",
            dim_x=512,
            dim_y=256,
            dim_z=128,
        )
        assert metadata.get_dimension_for_direction('XY') == 128


class TestQueueItemModel:
    """Tests for QueueItem model methods."""
    
    @pytest.mark.unit
    def test_from_treeview_values(self):
        """GIVEN string values, WHEN from_treeview_values, THEN creates QueueItem."""
        item = QueueItem.from_treeview_values(
            name="test",
            first="1",
            last="100",
            db_min="20",
            db_max="80",
            num_slices="50",
            refr_ind="1.0",
            disp_coeff="20",
            slice_dir="XZ",
            data_type="Processed",
            status="in queue",
            path="/path/file.oct",
        )
        assert item.name == "test"
        assert item.first_slice == 1
        assert item.last_slice == 100
        assert item.refractive_index == 1.0
    
    @pytest.mark.unit
    def test_to_treeview_values(self):
        """GIVEN QueueItem, WHEN to_treeview_values, THEN returns tuple."""
        item = QueueItem(
            name="test",
            first_slice=1,
            last_slice=100,
            db_min=20,
            db_max=80,
            num_slices=50,
            refractive_index=1.0,
            dispersion_coefficient=20,
            slice_direction='XZ',
            data_type='Processed',
            status='in queue',
            file_path='/path/file.oct',
        )
        values = item.to_treeview_values()
        assert isinstance(values, tuple)
        assert values[0] == "test"
        assert values[1] == 1
        assert values[11] == '/path/file.oct'
    
    @pytest.mark.unit
    def test_validation_slice_range(self):
        """GIVEN first > last, WHEN create QueueItem, THEN raises ValueError."""
        with pytest.raises(ValueError, match="first_slice"):
            QueueItem(
                name="test",
                first_slice=100,
                last_slice=1,
                db_min=20,
                db_max=80,
                num_slices=50,
                refractive_index=1.0,
                dispersion_coefficient=20,
                slice_direction='XZ',
                data_type='Processed',
                status='in queue',
                file_path='/path/file.oct',
            )
    
    @pytest.mark.unit
    def test_validation_db_range(self):
        """GIVEN db_min >= db_max, WHEN create QueueItem, THEN raises ValueError."""
        with pytest.raises(ValueError, match="db_min"):
            QueueItem(
                name="test",
                first_slice=1,
                last_slice=100,
                db_min=80,
                db_max=20,
                num_slices=50,
                refractive_index=1.0,
                dispersion_coefficient=20,
                slice_direction='XZ',
                data_type='Processed',
                status='in queue',
                file_path='/path/file.oct',
            )
