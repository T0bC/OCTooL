"""
RexView Pydantic Models

Data models for OCT export configuration and parameters.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional, Tuple, List
from pathlib import Path

from app.logic.rexview.validation import (
    db_range_error,
    slice_order_error,
    num_slices_error,
)


class SettingsConfig(BaseModel):
    """
    Configuration for OCT export settings from both global and custom settings panels.
    
    Combines settings from global_settings_panel and custom_settings_panel.
    """
    # Global settings
    resize_enabled: bool = Field(default=True, description="Apply aspect ratio correction")
    prefer_raw: bool = Field(default=True, description="Prefer raw spectral data over processed")
    advanced_filter: bool = Field(default=False, description="Apply advanced speckle filtering")
    export_format: Literal['.png', '.tiff'] = Field(default='.tiff', description="Output image format")
    averaging: Literal['none', 'incoherent', 'coherent'] = Field(
        default='coherent',
        description="A-scan averaging method"
    )
    tukey_window_size: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Tukey window parameter (0=rect, 1=Hann)"
    )
    show_error: bool = Field(default=False, description="Show error messages for missing text files")
    
    # Scale settings
    scale_enabled: bool = Field(default=True, description="Add scale bar to exported images")
    scale_length_um: int = Field(default=500, ge=1, description="Scale bar length in micrometers")
    scale_font_size: int = Field(default=30, ge=1, description="Scale bar text font size")
    
    # Custom settings - slice range
    first_slice: Optional[int] = Field(default=None, ge=1, description="First slice to export")
    last_slice: Optional[int] = Field(default=None, ge=1, description="Last slice to export")
    num_equidistant_slices: int = Field(default=25, ge=1, description="Number of equidistant slices")
    
    # Dynamic range
    db_min: int = Field(default=30, ge=0, le=50, description="Minimum dB value")
    db_max: int = Field(default=100, ge=50, le=120, description="Maximum dB value")
    
    # Dispersion
    dispersion_type: Literal['Quadratic', 'None'] = Field(
        default='Quadratic',
        description="Dispersion compensation type"
    )
    dispersion_coefficient: int = Field(
        default=-100,
        ge=-100,
        le=100,
        description="Dispersion coefficient value"
    )
    
    # Slice direction
    slice_direction: Literal['XZ', 'YZ', 'XY'] = Field(
        default='XZ',
        description="Image slice orientation"
    )
    
    # Refractive index
    refractive_index: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Refractive index correction factor"
    )
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
    @model_validator(mode='after')
    def validate_db_range(self) -> 'SettingsConfig':
        """Ensure db_min < db_max (see validation.db_range_error)."""
        error = db_range_error(self.db_min, self.db_max)
        if error:
            raise ValueError(error)
        return self
    
    @model_validator(mode='after')
    def validate_slice_range(self) -> 'SettingsConfig':
        """Ensure first_slice <= last_slice when both are set."""
        error = slice_order_error(self.first_slice, self.last_slice)
        if error:
            raise ValueError(error)
        return self
    
    @property
    def dispersion(self) -> Tuple[str, str]:
        """Return dispersion as tuple for compatibility with existing code."""
        return (self.dispersion_type, str(self.dispersion_coefficient))


class ExportConfig(BaseModel):
    """
    Configuration for OCT image export settings.
    
    Maps to the global settings panel state in the GUI.
    """
    # Image processing options
    resize_enabled: bool = Field(default=True, description="Apply aspect ratio correction")
    prefer_raw: bool = Field(default=True, description="Prefer raw spectral data over processed")
    advanced_filter: bool = Field(default=False, description="Apply advanced speckle filtering")
    
    # Export format
    export_format: Literal['.png', '.tiff'] = Field(default='.tiff', description="Output image format")
    
    # Averaging settings
    averaging: Literal['none', 'incoherent', 'coherent'] = Field(
        default='coherent', 
        description="A-scan averaging method"
    )
    
    # Window function
    tukey_window_size: float = Field(
        default=0.9, 
        ge=0.0, 
        le=1.0,
        description="Tukey window parameter (0=rect, 1=Hann)"
    )
    
    # Scale bar settings
    scale_enabled: bool = Field(default=True, description="Add scale bar to exported images")
    scale_length_um: int = Field(default=500, ge=1, description="Scale bar length in micrometers")
    scale_font_size: int = Field(default=30, ge=1, description="Scale bar text font size")
    
    # Parallel export
    worker_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of worker processes for parallel export (None = auto)",
    )
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    

class SliceExportParams(BaseModel):
    """
    Parameters for a single export job from the TreeView.
    
    Maps to a row in the export queue TreeView.
    """
    # File information
    file_path: str = Field(description="Path to the OCT file")
    name: str = Field(description="Export name/identifier")
    
    # Slice selection
    first_slice: int = Field(ge=1, description="First slice number (1-indexed)")
    last_slice: int = Field(ge=1, description="Last slice number (1-indexed)")
    num_slices: int = Field(ge=1, description="Number of slices to export")
    
    # Slice direction
    slice_direction: Literal['XZ', 'YZ', 'XY'] = Field(
        default='XZ',
        description="Image slice orientation"
    )
    
    # Dynamic range
    db_min: int = Field(default=20, description="Minimum dB value")
    db_max: int = Field(default=80, description="Maximum dB value")
    
    # Corrections
    refractive_index: float = Field(
        default=1.0, 
        ge=0.1, 
        le=5.0,
        description="Refractive index correction factor"
    )
    
    # Dispersion compensation
    dispersion: Tuple[str, str] = Field(
        default=('None', '0'),
        description="Dispersion compensation (type, coefficient)"
    )
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
    @model_validator(mode='after')
    def validate_slice_range(self) -> 'SliceExportParams':
        """Ensure first_slice <= last_slice and num_slices is valid."""
        error = slice_order_error(self.first_slice, self.last_slice)
        if error:
            raise ValueError(error)
        error = num_slices_error(self.first_slice, self.last_slice, self.num_slices)
        if error:
            raise ValueError(error)
        return self
    
    @property
    def export_dir_name(self) -> str:
        """Generate the export directory name."""
        return f"{self.name}_{self.num_slices}_Slices_{self.slice_direction}"
    
    def get_output_path(self, base_path: Path, exp_number: int) -> Path:
        """Get the full output directory path."""
        dir_name = f"{exp_number:02d}_{self.export_dir_name}"
        return base_path / dir_name


class ExportProgress(BaseModel):
    """Progress information for export operations."""
    current_item: int = Field(default=0, ge=0)
    total_items: int = Field(default=0, ge=0)
    current_slice: int = Field(default=0, ge=0)
    total_slices: int = Field(default=0, ge=0)
    status: str = Field(default='idle')
    
    @property
    def item_progress(self) -> float:
        """Return item progress as percentage (0-100)."""
        if self.total_items == 0:
            return 0.0
        return (self.current_item / self.total_items) * 100
    
    @property
    def slice_progress(self) -> float:
        """Return slice progress as percentage (0-100)."""
        if self.total_slices == 0:
            return 0.0
        return (self.current_slice / self.total_slices) * 100


class QueueItem(BaseModel):
    """
    Represents a single item in the export queue.
    
    Maps to a row in the TreeView table.
    """
    name: str = Field(description="File name without extension")
    first_slice: int = Field(default=1, ge=1, description="First slice to export (1-indexed)")
    last_slice: int = Field(ge=1, description="Last slice to export (1-indexed)")
    db_min: int = Field(default=20, description="Minimum dB value")
    db_max: int = Field(default=80, description="Maximum dB value")
    num_slices: int = Field(ge=1, description="Number of slices to export")
    refractive_index: float = Field(default=1.0, ge=0.1, le=5.0, description="Refractive index")
    dispersion_coefficient: int = Field(default=20, description="Dispersion coefficient")
    slice_direction: Literal['XZ', 'YZ', 'XY'] = Field(default='XZ', description="Image slice direction")
    data_type: str = Field(default='Processed', description="OCT data type")
    status: str = Field(default='in queue', description="Export status")
    file_path: str = Field(description="Full path to OCT file")
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
    @model_validator(mode='after')
    def validate_slice_range(self) -> 'QueueItem':
        """Ensure first_slice <= last_slice."""
        error = slice_order_error(self.first_slice, self.last_slice)
        if error:
            raise ValueError(error)
        return self
    
    @model_validator(mode='after')
    def validate_db_range(self) -> 'QueueItem':
        """Ensure db_min < db_max."""
        error = db_range_error(self.db_min, self.db_max)
        if error:
            raise ValueError(error)
        return self
    
    def to_treeview_values(self) -> tuple:
        """Convert to tuple for TreeView insertion."""
        return (
            self.name,
            self.first_slice,
            self.last_slice,
            self.db_min,
            self.db_max,
            self.num_slices,
            self.refractive_index,
            self.dispersion_coefficient,
            self.slice_direction,
            self.data_type,
            self.status,
            self.file_path,
        )


class FileMetadata(BaseModel):
    """
    Metadata extracted from an OCT file.
    
    Contains information needed to create queue entries.
    """
    file_path: str = Field(description="Full path to OCT file")
    file_name: str = Field(description="File name without extension")
    data_type: str = Field(description="OCT data type (Processed, Raw, etc.)")
    serial_number: Optional[str] = Field(default=None, description="Device serial number")
    dim_x: int = Field(default=1, ge=1, description="X dimension in pixels")
    dim_y: int = Field(default=1, ge=1, description="Y dimension in pixels")
    dim_z: int = Field(default=1, ge=1, description="Z dimension in pixels")
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
    def get_dimension_for_direction(self, direction: Literal['XZ', 'YZ', 'XY']) -> int:
        """Get the number of slices for a given slice direction."""
        direction_map = {
            'XZ': self.dim_y,
            'YZ': self.dim_x,
            'XY': self.dim_z,
        }
        return direction_map.get(direction, self.dim_y)


class ExportResult(BaseModel):
    """
    Result of exporting a single OCT file.

    Designed to be small and picklable so it can be returned across process
    boundaries from a parallel export worker.
    """
    file_path: str = Field(description="Full path to the source OCT file")
    exported_files: List[str] = Field(
        default_factory=list,
        description="Paths to the exported image files (as strings)",
    )
    failed_count: int = Field(
        default=0,
        ge=0,
        description="Number of slices that failed to export",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the export failed entirely",
    )


class ExportSettings(BaseModel):
    """
    Export settings parsed from a sidecar metadata file.
    
    Represents settings for a single export direction.
    """
    start: int = Field(ge=1, description="Start slice (1-indexed)")
    end: int = Field(ge=1, description="End slice (1-indexed)")
    num_equidistant_slices: int = Field(ge=1, description="Number of equidistant slices")
    refractive_index: float = Field(default=1.0, ge=0.1, le=5.0, description="Refractive index")
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
    @model_validator(mode='after')
    def validate_range(self) -> 'ExportSettings':
        """Ensure start <= end."""
        if self.start > self.end:
            raise ValueError(f"start ({self.start}) must be <= end ({self.end})")
        return self


class ImageDisplayConfig(BaseModel):
    """
    Configuration for OCT image preview display.
    
    Maps to the current UI state when displaying a preview image.
    """
    # Slice selection
    slice_index: int = Field(default=0, ge=0, description="Current slice index (0-indexed)")
    slice_direction: Literal['XZ', 'YZ', 'XY'] = Field(
        default='XZ',
        description="Image slice orientation"
    )
    
    # Dynamic range
    db_min: int = Field(default=20, description="Minimum dB value")
    db_max: int = Field(default=80, description="Maximum dB value")
    
    # Image processing options
    resize_enabled: bool = Field(default=True, description="Apply aspect ratio correction")
    refractive_index: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Refractive index correction factor"
    )
    
    # Scale bar settings
    scale_enabled: bool = Field(default=False, description="Add scale bar to image")
    scale_length_um: int = Field(default=500, ge=1, description="Scale bar length in micrometers")
    scale_font_size: int = Field(default=30, ge=1, description="Scale bar text font size")
    
    # Processing settings
    data_type: Literal['Processed', 'Raw', 'RawSpectra', 'RawSpectraAndProcessedIntensity'] = Field(
        default='Processed',
        description="OCT data type"
    )
    averaging: Literal['none', 'incoherent', 'coherent'] = Field(
        default='coherent',
        description="A-scan averaging method"
    )
    tukey_window_size: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Tukey window parameter (0=rect, 1=Hann)"
    )
    advanced_filter: bool = Field(default=False, description="Apply advanced speckle filtering")
    dispersion: Tuple[str, str] = Field(
        default=('None', '0'),
        description="Dispersion compensation (type, coefficient)"
    )
    
    # Canvas dimensions for fit calculation
    canvas_width: int = Field(default=1024, ge=1, description="Canvas width in pixels")
    canvas_height: int = Field(default=342, ge=1, description="Canvas height in pixels")
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
