"""
RexView Image Service

Pure business logic for OCT image preview display - no tkinter dependencies.
This service handles the core image processing logic extracted from image_panel.py.
"""
from typing import Optional, Tuple, Any
import numpy as np
from PIL import Image
from scipy import ndimage

from app.logic.rexview.models import ImageDisplayConfig
from app.logic.shared.models import OCTMetadata
from utils import oct_functions as octF


class ImageService:
    """
    Pure business logic for OCT image preview operations.
    
    This service encapsulates all image display logic without any GUI dependencies.
    It can be fully tested with pytest without requiring tkinter.
    """
    
    def __init__(self):
        self._archive = None
        self._metadata: Optional[OCTMetadata] = None
        self._image_stack: Optional[np.ndarray] = None
    
    @property
    def metadata(self) -> Optional[OCTMetadata]:
        """Return the currently loaded metadata."""
        return self._metadata
    
    @property
    def has_loaded_data(self) -> bool:
        """Check if OCT data is currently loaded."""
        return self._archive is not None and self._metadata is not None
    
    @property
    def total_slices(self) -> int:
        """Return total number of slices in the loaded data."""
        if self._metadata is None:
            return 0
        return self._metadata.dim_y
    
    def load_oct_file(self, file_path: str) -> OCTMetadata:
        """
        Load an OCT file and extract metadata.
        
        Args:
            file_path: Path to the OCT file
            
        Returns:
            OCTMetadata object with file information
        """
        # Close any existing archive
        if self._archive is not None:
            self._archive.close()
            self._archive = None
            self._image_stack = None
        
        # Open archive and read metadata
        self._archive = octF.unzipOCTData(file_path)
        xml_content = octF.readXMLContent(self._archive, 'Header.xml', 'xml')
        xml_dict = octF.getXMLAttributes(xml_content)
        self._metadata = OCTMetadata.from_xml_dict(xml_dict)
        
        return self._metadata
    
    def load_processed_stack(self, config: ImageDisplayConfig) -> np.ndarray:
        """
        Load the full processed image stack into memory.
        
        This is used for 'Processed' data type to avoid reloading
        on every slice change.
        
        Args:
            config: Display configuration with processing parameters
            
        Returns:
            3D numpy array of the image stack
        """
        if self._archive is None or self._metadata is None:
            raise ValueError("No OCT file loaded. Call load_oct_file() first.")
        
        xml_dict = self._metadata.to_xml_dict()
        
        self._image_stack = octF.createImageFromRaw(
            xmlDict=xml_dict,
            archive=self._archive,
            dBmin=config.db_min,
            dBmax=config.db_max,
            selDataType=config.data_type,
            averaging=config.averaging,
            spectral=config.slice_index,
            prefRaw='doesnt matter',
            tukeySize=config.tukey_window_size,
            advancedFilter='selected' if config.advanced_filter else '',
            dispersion=config.dispersion,
        )
        
        return self._image_stack
    
    def create_raw_slice(self, config: ImageDisplayConfig) -> np.ndarray:
        """
        Create a single slice from raw data.
        
        Used for 'Raw' data type where each slice is processed on demand.
        
        Args:
            config: Display configuration with processing parameters
            
        Returns:
            2D numpy array of the processed slice
        """
        if self._archive is None or self._metadata is None:
            raise ValueError("No OCT file loaded. Call load_oct_file() first.")
        
        xml_dict = self._metadata.to_xml_dict()
        
        return octF.createImageFromRaw(
            xmlDict=xml_dict,
            archive=self._archive,
            dBmin=config.db_min,
            dBmax=config.db_max,
            selDataType=config.data_type,
            averaging=config.averaging,
            spectral=config.slice_index,
            prefRaw='doesnt matter',
            tukeySize=config.tukey_window_size,
            advancedFilter='selected' if config.advanced_filter else '',
            dispersion=config.dispersion,
        )
    
    def extract_slice(
        self,
        image_stack: np.ndarray,
        slice_index: int,
    ) -> np.ndarray:
        """
        Extract a 2D slice from a 3D image stack.
        
        Args:
            image_stack: 3D numpy array (slices, height, width)
            slice_index: Index of slice to extract (0-indexed)
            
        Returns:
            2D numpy array of the extracted slice
        """
        if image_stack.ndim == 2:
            return image_stack
        return image_stack[slice_index, :, :]
    
    def apply_resize_correction(
        self,
        img: np.ndarray,
        slice_direction: str,
        resize_factor_x: float,
        resize_factor_y: float,
    ) -> np.ndarray:
        """
        Apply aspect ratio correction based on slice direction.
        
        Args:
            img: 2D numpy array
            slice_direction: 'XZ', 'YZ', or 'XY'
            resize_factor_x: X-axis resize factor from metadata
            resize_factor_y: Y-axis resize factor from metadata
            
        Returns:
            Resized 2D numpy array
        """
        if slice_direction == 'XZ':
            return ndimage.zoom(img, zoom=(1, resize_factor_x), order=0)
        elif slice_direction == 'YZ':
            return ndimage.zoom(img, zoom=(1, resize_factor_y), order=0)
        elif slice_direction == 'XY':
            return ndimage.zoom(img, zoom=(resize_factor_y, resize_factor_x), order=0)
        return img
    
    def apply_refractive_index_correction(
        self,
        img: np.ndarray,
        refractive_index: float,
    ) -> np.ndarray:
        """
        Apply refractive index correction to the image.
        
        Args:
            img: 2D numpy array
            refractive_index: Refractive index correction factor
            
        Returns:
            Corrected 2D numpy array
        """
        if refractive_index == 1.0:
            return img
        return ndimage.zoom(img, zoom=(refractive_index, 1), order=0)
    
    def add_scale_bar(
        self,
        img: Image.Image,
        scale_length_um: int,
        font_size: int,
        slice_direction: str,
    ) -> Image.Image:
        """
        Add a scale bar to the image.
        
        Args:
            img: PIL Image
            scale_length_um: Scale bar length in micrometers
            font_size: Font size for scale text
            slice_direction: 'XZ', 'YZ', or 'XY'
            
        Returns:
            PIL Image with scale bar
        """
        if self._metadata is None:
            raise ValueError("No metadata loaded. Call load_oct_file() first.")
        
        xml_dict = self._metadata.to_xml_dict()
        return octF.insertScale(
            img=img,
            scaleSize=scale_length_um,
            xmlDict=xml_dict,
            fontSize=font_size,
            imgSliceDir=slice_direction,
        )
    
    def resize_to_fit_canvas(
        self,
        img: Image.Image,
        canvas_width: int,
        canvas_height: int,
    ) -> Image.Image:
        """
        Resize image to fit within canvas while maintaining aspect ratio.
        
        The image is scaled to fit the canvas height.
        
        Args:
            img: PIL Image
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
            
        Returns:
            Resized PIL Image
        """
        if canvas_height <= 0 or img.size[1] <= 0:
            return img
        
        aspect_ratio = img.size[0] / img.size[1]
        new_width = int(canvas_height * aspect_ratio)
        new_height = canvas_height
        
        return img.resize((new_width, new_height), Image.LANCZOS)
    
    def calculate_canvas_position(
        self,
        img_width: int,
        canvas_width: int,
    ) -> int:
        """
        Calculate X position to center image on canvas.
        
        Args:
            img_width: Image width in pixels
            canvas_width: Canvas width in pixels
            
        Returns:
            X position for image placement
        """
        return (canvas_width // 2) - (img_width // 2)
    
    def process_preview_image(
        self,
        config: ImageDisplayConfig,
        image_stack: Optional[np.ndarray] = None,
    ) -> Tuple[Image.Image, int]:
        """
        Process a complete preview image ready for display.
        
        This is the main method that combines all processing steps:
        1. Extract slice from stack (or create from raw)
        2. Apply resize correction
        3. Apply refractive index correction
        4. Add scale bar (optional)
        5. Resize to fit canvas
        6. Calculate canvas position
        
        Args:
            config: Display configuration
            image_stack: Pre-loaded image stack (for Processed data)
                        If None, creates slice from raw data
            
        Returns:
            Tuple of (PIL Image, x_position for canvas)
        """
        if self._metadata is None:
            raise ValueError("No metadata loaded. Call load_oct_file() first.")
        
        # Get the 2D slice
        if config.data_type == 'Processed' and image_stack is not None:
            img_2d = self.extract_slice(image_stack, config.slice_index)
        else:
            img_2d = self.create_raw_slice(config)
        
        # Apply resize correction if enabled
        if config.resize_enabled:
            img_2d = self.apply_resize_correction(
                img_2d,
                config.slice_direction,
                self._metadata.img_resize_factor_x,
                self._metadata.img_resize_factor_y,
            )
        
        # Apply refractive index correction
        if config.refractive_index != 1.0:
            img_2d = self.apply_refractive_index_correction(
                img_2d,
                config.refractive_index,
            )
        
        # Convert to PIL Image
        pil_img = Image.fromarray(img_2d)
        
        # Add scale bar if enabled
        if config.scale_enabled:
            pil_img = self.add_scale_bar(
                pil_img,
                config.scale_length_um,
                config.scale_font_size,
                config.slice_direction,
            )
        
        # Resize to fit canvas
        pil_img = self.resize_to_fit_canvas(
            pil_img,
            config.canvas_width,
            config.canvas_height,
        )
        
        # Calculate position
        x_position = self.calculate_canvas_position(
            pil_img.size[0],
            config.canvas_width,
        )
        
        return pil_img, x_position
    
    def navigate_slice(
        self,
        current_index: int,
        direction: int,
        total_slices: int,
    ) -> int:
        """
        Calculate new slice index for navigation.
        
        Args:
            current_index: Current slice index (0-indexed)
            direction: Direction to move (-1 for previous, +1 for next)
            total_slices: Total number of slices
            
        Returns:
            New slice index (clamped to valid range)
        """
        new_index = current_index + direction
        return max(0, min(new_index, total_slices - 1))
    
    def get_middle_slice_index(self) -> int:
        """
        Get the index of the middle slice.
        
        Returns:
            Middle slice index (0-indexed)
        """
        if self._metadata is None:
            return 0
        return self._metadata.dim_y // 2
    
    def close(self):
        """Close the archive and release resources."""
        if self._archive is not None:
            self._archive.close()
            self._archive = None
        self._metadata = None
        self._image_stack = None
