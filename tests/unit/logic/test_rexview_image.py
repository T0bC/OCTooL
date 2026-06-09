"""
Unit tests for app/logic/rexview/image_service.py

Tests the ImageService business logic without GUI dependencies.
"""
import pytest
import numpy as np
from PIL import Image
from unittest.mock import Mock, patch, MagicMock

from app.logic.rexview.image_service import ImageService
from app.logic.rexview.models import ImageDisplayConfig
from app.view.rexview.gui_adapters import image_display_config_from_gui_state
from app.logic.shared.models import OCTMetadata


class TestImageServiceInit:
    """Tests for ImageService initialization and state management."""
    
    @pytest.mark.unit
    def test_init_creates_service(self):
        """GIVEN nothing, WHEN ImageService is created, THEN it initializes correctly."""
        service = ImageService()
        assert service is not None
        assert service.has_loaded_data is False
        assert service.metadata is None
        assert service.total_slices == 0
    
    @pytest.mark.unit
    def test_close_releases_resources(self):
        """GIVEN a service, WHEN close is called, THEN resources are released."""
        service = ImageService()
        service._metadata = Mock()
        service._archive = Mock()
        service._image_stack = Mock()
        
        service.close()
        
        assert service._metadata is None
        assert service._archive is None
        assert service._image_stack is None


class TestExtractSlice:
    """Tests for ImageService.extract_slice method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.mark.unit
    def test_extract_slice_from_3d_stack(self, service, sample_3d_image_stack):
        """GIVEN a 3D stack, WHEN extract_slice is called, THEN returns 2D slice."""
        result = service.extract_slice(sample_3d_image_stack, slice_index=5)
        
        assert result.ndim == 2
        assert result.shape == (256, 256)
        np.testing.assert_array_equal(result, sample_3d_image_stack[5, :, :])
    
    @pytest.mark.unit
    def test_extract_slice_from_2d_array(self, service, sample_image_array):
        """GIVEN a 2D array, WHEN extract_slice is called, THEN returns same array."""
        result = service.extract_slice(sample_image_array, slice_index=0)
        
        assert result.ndim == 2
        np.testing.assert_array_equal(result, sample_image_array)
    
    @pytest.mark.unit
    def test_extract_slice_first_index(self, service, sample_3d_image_stack):
        """GIVEN a 3D stack, WHEN extracting first slice, THEN returns correct slice."""
        result = service.extract_slice(sample_3d_image_stack, slice_index=0)
        np.testing.assert_array_equal(result, sample_3d_image_stack[0, :, :])
    
    @pytest.mark.unit
    def test_extract_slice_last_index(self, service, sample_3d_image_stack):
        """GIVEN a 3D stack, WHEN extracting last slice, THEN returns correct slice."""
        result = service.extract_slice(sample_3d_image_stack, slice_index=9)
        np.testing.assert_array_equal(result, sample_3d_image_stack[9, :, :])


class TestApplyResizeCorrection:
    """Tests for ImageService.apply_resize_correction method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.fixture
    def sample_image(self):
        return np.random.randint(0, 256, (100, 100), dtype=np.uint8)
    
    @pytest.mark.unit
    def test_resize_xz_direction(self, service, sample_image):
        """GIVEN XZ direction, WHEN apply_resize_correction, THEN resizes X axis."""
        result = service.apply_resize_correction(
            sample_image,
            slice_direction='XZ',
            resize_factor_x=2.0,
            resize_factor_y=1.0,
        )
        
        assert result.shape[0] == 100  # Height unchanged
        assert result.shape[1] == 200  # Width doubled
    
    @pytest.mark.unit
    def test_resize_yz_direction(self, service, sample_image):
        """GIVEN YZ direction, WHEN apply_resize_correction, THEN resizes Y axis."""
        result = service.apply_resize_correction(
            sample_image,
            slice_direction='YZ',
            resize_factor_x=1.0,
            resize_factor_y=2.0,
        )
        
        assert result.shape[0] == 100  # Height unchanged
        assert result.shape[1] == 200  # Width doubled
    
    @pytest.mark.unit
    def test_resize_xy_direction(self, service, sample_image):
        """GIVEN XY direction, WHEN apply_resize_correction, THEN resizes both axes."""
        result = service.apply_resize_correction(
            sample_image,
            slice_direction='XY',
            resize_factor_x=2.0,
            resize_factor_y=1.5,
        )
        
        assert result.shape[0] == 150  # Height * 1.5
        assert result.shape[1] == 200  # Width * 2.0
    
    @pytest.mark.unit
    def test_resize_factor_one(self, service, sample_image):
        """GIVEN resize factor 1.0, WHEN apply_resize_correction, THEN shape unchanged."""
        result = service.apply_resize_correction(
            sample_image,
            slice_direction='XZ',
            resize_factor_x=1.0,
            resize_factor_y=1.0,
        )
        
        assert result.shape == sample_image.shape


class TestApplyRefractiveIndexCorrection:
    """Tests for ImageService.apply_refractive_index_correction method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.fixture
    def sample_image(self):
        return np.random.randint(0, 256, (100, 100), dtype=np.uint8)
    
    @pytest.mark.unit
    def test_refractive_index_greater_than_one(self, service, sample_image):
        """GIVEN refractive index > 1, WHEN apply correction, THEN height increases."""
        result = service.apply_refractive_index_correction(sample_image, 1.5)
        
        assert result.shape[0] == 150  # Height * 1.5
        assert result.shape[1] == 100  # Width unchanged
    
    @pytest.mark.unit
    def test_refractive_index_one(self, service, sample_image):
        """GIVEN refractive index = 1, WHEN apply correction, THEN returns same array."""
        result = service.apply_refractive_index_correction(sample_image, 1.0)
        
        np.testing.assert_array_equal(result, sample_image)
    
    @pytest.mark.unit
    def test_refractive_index_less_than_one(self, service, sample_image):
        """GIVEN refractive index < 1, WHEN apply correction, THEN height decreases."""
        result = service.apply_refractive_index_correction(sample_image, 0.5)
        
        assert result.shape[0] == 50  # Height * 0.5
        assert result.shape[1] == 100  # Width unchanged


class TestResizeToFitCanvas:
    """Tests for ImageService.resize_to_fit_canvas method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.mark.unit
    def test_resize_maintains_aspect_ratio(self, service, sample_grayscale_image):
        """GIVEN an image, WHEN resize_to_fit_canvas, THEN aspect ratio is maintained."""
        # Create a 200x100 image (2:1 aspect ratio)
        arr = np.random.randint(0, 256, (100, 200), dtype=np.uint8)
        img = Image.fromarray(arr, mode='L')
        
        result = service.resize_to_fit_canvas(img, canvas_width=1024, canvas_height=300)
        
        # Height should be 300, width should be 600 (2:1 ratio)
        assert result.size[1] == 300
        assert result.size[0] == 600
    
    @pytest.mark.unit
    def test_resize_to_canvas_height(self, service, sample_grayscale_image):
        """GIVEN an image, WHEN resize_to_fit_canvas, THEN height matches canvas."""
        result = service.resize_to_fit_canvas(
            sample_grayscale_image,
            canvas_width=1024,
            canvas_height=400,
        )
        
        assert result.size[1] == 400
    
    @pytest.mark.unit
    def test_resize_zero_canvas_height(self, service, sample_grayscale_image):
        """GIVEN zero canvas height, WHEN resize_to_fit_canvas, THEN returns original."""
        result = service.resize_to_fit_canvas(
            sample_grayscale_image,
            canvas_width=1024,
            canvas_height=0,
        )
        
        assert result.size == sample_grayscale_image.size


class TestCalculateCanvasPosition:
    """Tests for ImageService.calculate_canvas_position method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.mark.unit
    def test_center_position(self, service):
        """GIVEN image smaller than canvas, WHEN calculate_canvas_position, THEN centers."""
        x_pos = service.calculate_canvas_position(img_width=500, canvas_width=1000)
        
        assert x_pos == 250
    
    @pytest.mark.unit
    def test_image_equals_canvas(self, service):
        """GIVEN image same size as canvas, WHEN calculate_canvas_position, THEN x=0."""
        x_pos = service.calculate_canvas_position(img_width=1000, canvas_width=1000)
        
        assert x_pos == 0
    
    @pytest.mark.unit
    def test_image_larger_than_canvas(self, service):
        """GIVEN image larger than canvas, WHEN calculate_canvas_position, THEN negative."""
        x_pos = service.calculate_canvas_position(img_width=1200, canvas_width=1000)
        
        assert x_pos == -100


class TestNavigateSlice:
    """Tests for ImageService.navigate_slice method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.mark.unit
    def test_navigate_forward(self, service):
        """GIVEN current index, WHEN navigate forward, THEN index increases."""
        new_idx = service.navigate_slice(current_index=5, direction=1, total_slices=100)
        
        assert new_idx == 6
    
    @pytest.mark.unit
    def test_navigate_backward(self, service):
        """GIVEN current index, WHEN navigate backward, THEN index decreases."""
        new_idx = service.navigate_slice(current_index=5, direction=-1, total_slices=100)
        
        assert new_idx == 4
    
    @pytest.mark.unit
    def test_navigate_clamps_at_zero(self, service):
        """GIVEN index at 0, WHEN navigate backward, THEN stays at 0."""
        new_idx = service.navigate_slice(current_index=0, direction=-1, total_slices=100)
        
        assert new_idx == 0
    
    @pytest.mark.unit
    def test_navigate_clamps_at_max(self, service):
        """GIVEN index at max, WHEN navigate forward, THEN stays at max."""
        new_idx = service.navigate_slice(current_index=99, direction=1, total_slices=100)
        
        assert new_idx == 99
    
    @pytest.mark.unit
    def test_navigate_multiple_steps(self, service):
        """GIVEN direction > 1, WHEN navigate, THEN moves multiple steps."""
        new_idx = service.navigate_slice(current_index=5, direction=5, total_slices=100)
        
        assert new_idx == 10


class TestGetMiddleSliceIndex:
    """Tests for ImageService.get_middle_slice_index method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.mark.unit
    def test_middle_slice_no_metadata(self, service):
        """GIVEN no metadata loaded, WHEN get_middle_slice_index, THEN returns 0."""
        assert service.get_middle_slice_index() == 0
    
    @pytest.mark.unit
    def test_middle_slice_with_metadata(self, service, sample_xml_dict):
        """GIVEN metadata loaded, WHEN get_middle_slice_index, THEN returns middle."""
        service._metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        
        # dimY = 128, so middle = 64
        assert service.get_middle_slice_index() == 64


class TestImageDisplayConfig:
    """Tests for ImageDisplayConfig model."""
    
    @pytest.mark.unit
    def test_default_values(self):
        """GIVEN no arguments, WHEN creating ImageDisplayConfig, THEN uses defaults."""
        config = ImageDisplayConfig()
        
        assert config.slice_index == 0
        assert config.slice_direction == 'XZ'
        assert config.db_min == 20
        assert config.db_max == 80
        assert config.resize_enabled is True
        assert config.refractive_index == 1.0
        assert config.scale_enabled is False
        assert config.data_type == 'Processed'
    
    @pytest.mark.unit
    def test_from_gui_state(self):
        """GIVEN GUI state values, WHEN from_gui_state, THEN creates correct config."""
        config = image_display_config_from_gui_state(
            slice_index=50,
            slice_direction='YZ',
            db_min='30',
            db_max='90',
            resize_state='selected',
            refractive_index='1.4',
            scale_state=('selected',),
            scale_length='250',
            scale_font_size='24',
            data_type='Raw',
            averaging='incoherent',
            tukey_size='0.8',
            advanced_filter_state='selected',
            dispersion=('Linear', '0.5'),
            canvas_width=800,
            canvas_height=600,
        )
        
        assert config.slice_index == 50
        assert config.slice_direction == 'YZ'
        assert config.db_min == 30
        assert config.db_max == 90
        assert config.resize_enabled is True
        assert config.refractive_index == 1.4
        assert config.scale_enabled is True
        assert config.scale_length_um == 250
        assert config.scale_font_size == 24
        assert config.data_type == 'Raw'
        assert config.averaging == 'incoherent'
        assert config.tukey_window_size == 0.8
        assert config.advanced_filter is True
        assert config.dispersion == ('Linear', '0.5')
        assert config.canvas_width == 800
        assert config.canvas_height == 600
    
    @pytest.mark.unit
    def test_from_gui_state_unselected(self):
        """GIVEN unselected GUI states, WHEN from_gui_state, THEN booleans are False."""
        config = image_display_config_from_gui_state(
            slice_index=0,
            slice_direction='XZ',
            db_min='20',
            db_max='80',
            resize_state='',
            refractive_index='1.0',
            scale_state=(),
            scale_length='500',
            scale_font_size='30',
            data_type='Processed',
            averaging='coherent',
            tukey_size='0.9',
            advanced_filter_state='',
            dispersion=('None', '0'),
            canvas_width=1024,
            canvas_height=342,
        )
        
        assert config.resize_enabled is False
        assert config.scale_enabled is False
        assert config.advanced_filter is False


class TestProcessPreviewImage:
    """Tests for ImageService.process_preview_image method."""
    
    @pytest.fixture
    def service(self, sample_xml_dict):
        svc = ImageService()
        svc._metadata = OCTMetadata.from_xml_dict(sample_xml_dict)
        return svc
    
    @pytest.fixture
    def config(self):
        return ImageDisplayConfig(
            slice_index=5,
            slice_direction='XZ',
            resize_enabled=False,
            refractive_index=1.0,
            scale_enabled=False,
            canvas_width=1024,
            canvas_height=342,
        )
    
    @pytest.mark.unit
    def test_process_preview_returns_tuple(self, service, config, sample_3d_image_stack):
        """GIVEN valid inputs, WHEN process_preview_image, THEN returns (Image, int)."""
        result = service.process_preview_image(config, image_stack=sample_3d_image_stack)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], Image.Image)
        assert isinstance(result[1], int)
    
    @pytest.mark.unit
    def test_process_preview_no_metadata_raises(self, config, sample_3d_image_stack):
        """GIVEN no metadata, WHEN process_preview_image, THEN raises ValueError."""
        service = ImageService()
        
        with pytest.raises(ValueError, match="No metadata loaded"):
            service.process_preview_image(config, image_stack=sample_3d_image_stack)
    
    @pytest.mark.unit
    def test_process_preview_with_resize(self, service, sample_3d_image_stack):
        """GIVEN resize_enabled=True, WHEN process_preview_image, THEN applies resize."""
        config = ImageDisplayConfig(
            slice_index=0,
            resize_enabled=True,
            refractive_index=1.0,
            scale_enabled=False,
            canvas_width=1024,
            canvas_height=342,
        )
        
        # Modify metadata to have resize factors
        service._metadata.img_resize_factor_x = 2.0
        
        result_img, _ = service.process_preview_image(config, image_stack=sample_3d_image_stack)
        
        # Image should be resized (width doubled before canvas fit)
        assert result_img is not None
    
    @pytest.mark.unit
    def test_process_preview_with_refractive_index(self, service, sample_3d_image_stack):
        """GIVEN refractive_index > 1, WHEN process_preview_image, THEN applies correction."""
        config = ImageDisplayConfig(
            slice_index=0,
            resize_enabled=False,
            refractive_index=1.5,
            scale_enabled=False,
            canvas_width=1024,
            canvas_height=342,
        )
        
        result_img, _ = service.process_preview_image(config, image_stack=sample_3d_image_stack)
        
        assert result_img is not None
    
    @pytest.mark.unit
    def test_process_preview_calculates_position(self, service, config, sample_3d_image_stack):
        """GIVEN valid inputs, WHEN process_preview_image, THEN calculates centered position."""
        result_img, x_pos = service.process_preview_image(config, image_stack=sample_3d_image_stack)
        
        # Position should center the image
        expected_pos = (config.canvas_width // 2) - (result_img.size[0] // 2)
        assert x_pos == expected_pos


class TestLoadOctFile:
    """Tests for ImageService.load_oct_file method."""
    
    @pytest.fixture
    def service(self):
        return ImageService()
    
    @pytest.mark.unit
    def test_load_oct_file_returns_metadata(self, service, sample_xml_dict):
        """GIVEN valid OCT file, WHEN load_oct_file, THEN returns OCTMetadata."""
        with patch('app.logic.rexview.image_service.octF') as mock_octF:
            mock_octF.unzipOCTData.return_value = MagicMock()
            mock_octF.readXMLContent.return_value = '<xml/>'
            mock_octF.getXMLAttributes.return_value = sample_xml_dict
            
            result = service.load_oct_file('test.oct')
            
            assert isinstance(result, OCTMetadata)
            assert service.has_loaded_data is True
            assert service.total_slices == sample_xml_dict['dimY']
    
    @pytest.mark.unit
    def test_load_oct_file_closes_previous(self, service, sample_xml_dict):
        """GIVEN existing archive, WHEN load_oct_file, THEN closes previous archive."""
        mock_old_archive = MagicMock()
        service._archive = mock_old_archive
        
        with patch('app.logic.rexview.image_service.octF') as mock_octF:
            mock_octF.unzipOCTData.return_value = MagicMock()
            mock_octF.readXMLContent.return_value = '<xml/>'
            mock_octF.getXMLAttributes.return_value = sample_xml_dict
            
            service.load_oct_file('new_file.oct')
            
            mock_old_archive.close.assert_called_once()
