"""
RexView Pydantic Models

Data models for OCT export configuration and parameters.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional, Tuple
from pathlib import Path


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
    
    model_config = {
        'frozen': False,
        'validate_assignment': True,
    }
    
    @classmethod
    def from_gui_state(
        cls,
        resize_state: str,
        prefer_raw_state: tuple,
        advanced_filter_state: str,
        export_format: str,
        averaging: str,
        tukey_size: str,
        scale_state: tuple,
        scale_length: str,
        scale_font_size: str,
    ) -> 'ExportConfig':
        """
        Create ExportConfig from GUI widget states.
        
        This factory method handles the conversion from tkinter widget
        state strings to proper Python types.
        """
        return cls(
            resize_enabled=resize_state == 'selected',
            prefer_raw=prefer_raw_state == ('selected',),
            advanced_filter=advanced_filter_state == 'selected',
            export_format=export_format,
            averaging=averaging,
            tukey_window_size=float(tukey_size),
            scale_enabled=scale_state == ('selected',),
            scale_length_um=int(scale_length),
            scale_font_size=int(scale_font_size),
        )


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
        if self.first_slice > self.last_slice:
            raise ValueError(f"first_slice ({self.first_slice}) must be <= last_slice ({self.last_slice})")
        max_possible = self.last_slice - self.first_slice + 1
        if self.num_slices > max_possible:
            raise ValueError(f"num_slices ({self.num_slices}) exceeds available range ({max_possible})")
        return self
    
    @classmethod
    def from_treeview_row(
        cls,
        path: str,
        name: str,
        first: str,
        last: str,
        num_slices: str,
        slice_dir: str,
        db_min: str,
        db_max: str,
        refr_ind: str,
        dispersion: Tuple[str, str],
    ) -> 'SliceExportParams':
        """
        Create SliceExportParams from TreeView row values.
        
        This factory method handles the conversion from string values
        to proper Python types.
        """
        return cls(
            file_path=path,
            name=name,
            first_slice=int(first),
            last_slice=int(last),
            num_slices=int(num_slices),
            slice_direction=slice_dir,
            db_min=int(db_min),
            db_max=int(db_max),
            refractive_index=float(refr_ind),
            dispersion=dispersion,
        )
    
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
    data_type: Literal['Processed', 'Raw'] = Field(
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
    
    @classmethod
    def from_gui_state(
        cls,
        slice_index: int,
        slice_direction: str,
        db_min: str,
        db_max: str,
        resize_state: str,
        refractive_index: str,
        scale_state: tuple,
        scale_length: str,
        scale_font_size: str,
        data_type: str,
        averaging: str,
        tukey_size: str,
        advanced_filter_state: str,
        dispersion: Tuple[str, str],
        canvas_width: int,
        canvas_height: int,
    ) -> 'ImageDisplayConfig':
        """
        Create ImageDisplayConfig from GUI widget states.
        
        This factory method handles the conversion from tkinter widget
        state strings to proper Python types.
        """
        return cls(
            slice_index=slice_index,
            slice_direction=slice_direction,
            db_min=int(db_min),
            db_max=int(db_max),
            resize_enabled=resize_state == 'selected',
            refractive_index=float(refractive_index),
            scale_enabled=scale_state == ('selected',),
            scale_length_um=int(scale_length),
            scale_font_size=int(scale_font_size),
            data_type=data_type,
            averaging=averaging,
            tukey_window_size=float(tukey_size),
            advanced_filter=advanced_filter_state == 'selected',
            dispersion=dispersion,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        )
