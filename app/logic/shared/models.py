"""
Shared Pydantic Models

Common data models used across OCTooL modules.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Tuple


class OCTMetadata(BaseModel):
    """
    Pydantic model for OCT file metadata extracted from Header.xml.
    
    This model validates and structures the metadata dictionary
    returned by oct_functions.getXMLAttributes().
    """
    # Data type information
    data_type: str = Field(alias='dataType')
    xml_data_type: Optional[dict] = Field(default=None, alias='xmlDataType')
    
    # Pixel dimensions
    dim_x: int = Field(ge=1, alias='dimX')
    dim_y: int = Field(ge=1, alias='dimY')
    dim_z: int = Field(ge=1, alias='dimZ')
    img_size: Tuple[int, int] = Field(alias='imgSize')
    
    # Physical dimensions (mm)
    img_size_mm_x: Optional[float] = Field(default=None, alias='imgSizemmX')
    img_size_mm_y: Optional[float] = Field(default=None, alias='imgSizemmY')
    img_size_mm_z: Optional[float] = Field(default=None, alias='imgSizemmZ')
    
    # Pixel spacing (µm)
    spacing_x: float = Field(ge=0, alias='spacingX')
    spacing_y: float = Field(ge=0, alias='spacingY')
    spacing_z: float = Field(ge=0, alias='spacingZ')
    
    # Resize factors
    img_resize_factor_x: float = Field(default=1.0, alias='imgResizeFactorX')
    img_resize_factor_y: float = Field(default=1.0, alias='imgResizeFactorY')
    
    # Study information
    study_name: str = Field(default='', alias='studyName')
    exp_number: int = Field(ge=0, alias='expNumber')
    
    # Raw data parameters
    n_line: Optional[int] = Field(default=None, alias='Nline')
    n_apo: Optional[int] = Field(default=None, alias='Napo')
    n_x: Optional[int] = Field(default=None, alias='Nx')
    offs_scale: Optional[float] = Field(default=None, alias='offsScale')
    a_scan_av: int = Field(default=1, alias='aScanAv')
    
    # Device information
    model: Optional[str] = Field(default=None, alias='Modell')
    serial_number: Optional[str] = Field(default=None, alias='Serialnumber')
    sensitivity: Optional[str] = Field(default=None, alias='Sensitivity')
    probe_name: Optional[str] = Field(default=None, alias='Probe_Name')
    wavelength: Optional[str] = Field(default=None, alias='Wavelength')
    acquisition_datetime: Optional[str] = Field(default=None, alias='Acquisition_DateTime')
    scan_duration: Optional[float] = Field(default=None, alias='Scan_Duration')
    software_version: Optional[str] = Field(default=None, alias='Software_Version')
    
    # Scan type
    is_3d: bool = Field(default=False, alias='is3D')
    
    # Video image dimensions
    video_image_z: int = Field(default=0, alias='videoImageZ')
    video_image_x: int = Field(default=0, alias='videoImageX')
    
    model_config = {
        'populate_by_name': True,
        'extra': 'allow',  # Allow extra fields from xmlDict
    }
    
    @classmethod
    def from_xml_dict(cls, xml_dict: dict) -> 'OCTMetadata':
        """Create OCTMetadata from the dictionary returned by getXMLAttributes()."""
        return cls.model_validate(xml_dict)
    
    def to_xml_dict(self) -> dict:
        """Convert back to the original xmlDict format for backward compatibility."""
        return self.model_dump(by_alias=True)
    
    @property
    def has_raw_data(self) -> bool:
        """Check if raw spectral data is available."""
        return self.data_type in ('RawSpectra', 'RawSpectraAndProcessedIntensity')
    
    @property
    def has_processed_data(self) -> bool:
        """Check if processed intensity data is available."""
        return self.data_type in ('Processed', 'RawSpectraAndProcessedIntensity')
