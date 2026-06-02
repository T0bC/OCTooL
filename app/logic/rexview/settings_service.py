"""
RexView Settings Service

Pure business logic for OCT export settings validation and defaults - no tkinter dependencies.
This service handles the core settings logic extracted from global_settings_panel.py and custom_settings_panel.py.
"""
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from app.logic.rexview.models import SettingsConfig


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class SettingsService:
    """
    Pure business logic for OCT export settings operations.
    
    This service encapsulates all settings validation and defaults logic
    without any GUI dependencies. It can be fully tested with pytest
    without requiring tkinter.
    """
    
    # Default values matching the GUI defaults
    DEFAULTS = {
        'resize_enabled': True,
        'prefer_raw': True,
        'advanced_filter': False,
        'export_format': '.tiff',
        'averaging': 'coherent',
        'tukey_window_size': 0.9,
        'show_error': False,
        'scale_enabled': True,
        'scale_length_um': 500,
        'scale_font_size': 30,
        'num_equidistant_slices': 25,
        'db_min': 30,
        'db_max': 100,
        'dispersion_type': 'Quadratic',
        'dispersion_coefficient': -100,
        'slice_direction': 'XZ',
        'refractive_index': 1.0,
    }
    
    # Valid options for each setting
    VALID_OPTIONS = {
        'export_format': ['.png', '.tiff'],
        'averaging': ['none', 'incoherent', 'coherent'],
        'tukey_window_size': [0.0, 0.3, 0.5, 0.7, 0.9, 1.0],
        'dispersion_type': ['Quadratic', 'None'],
        'slice_direction': ['XZ', 'YZ', 'XY'],
    }
    
    # Value ranges
    VALUE_RANGES = {
        'tukey_window_size': (0.0, 1.0),
        'scale_length_um': (1, 10000),
        'scale_font_size': (1, 200),
        'db_min': (0, 50),
        'db_max': (50, 120),
        'dispersion_coefficient': (-100, 100),
        'refractive_index': (0.1, 5.0),
        'num_equidistant_slices': (1, 10000),
    }
    
    def __init__(self):
        pass
    
    def get_defaults(self) -> SettingsConfig:
        """
        Return default configuration.
        
        Returns:
            SettingsConfig with all default values
        """
        return SettingsConfig(**self.DEFAULTS)
    
    def get_default_value(self, setting_name: str) -> Any:
        """
        Get the default value for a specific setting.
        
        Args:
            setting_name: Name of the setting
            
        Returns:
            Default value for the setting
            
        Raises:
            KeyError: If setting_name is not a valid setting
        """
        if setting_name not in self.DEFAULTS:
            raise KeyError(f"Unknown setting: {setting_name}")
        return self.DEFAULTS[setting_name]
    
    def validate_export_config(self, config: SettingsConfig) -> ValidationResult:
        """
        Validate a complete export configuration.
        
        Checks for:
        - Valid value ranges
        - Consistent settings combinations
        - Required dependencies (e.g., scale settings when scale enabled)
        
        Args:
            config: SettingsConfig to validate
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        # Validate dB range
        if config.db_min >= config.db_max:
            errors.append(f"db_min ({config.db_min}) must be less than db_max ({config.db_max})")
        
        # Validate slice range if both are set
        if config.first_slice is not None and config.last_slice is not None:
            if config.first_slice > config.last_slice:
                errors.append(f"first_slice ({config.first_slice}) must be <= last_slice ({config.last_slice})")
        
        # Validate scale settings when scale is enabled
        if config.scale_enabled:
            if config.scale_length_um <= 0:
                errors.append("scale_length_um must be positive when scale is enabled")
            if config.scale_font_size <= 0:
                errors.append("scale_font_size must be positive when scale is enabled")
        
        # Validate dispersion coefficient when dispersion is enabled
        if config.dispersion_type == 'Quadratic':
            if not (-100 <= config.dispersion_coefficient <= 100):
                errors.append(f"dispersion_coefficient ({config.dispersion_coefficient}) must be between -100 and 100")
        
        # Validate refractive index
        if not (0.1 <= config.refractive_index <= 5.0):
            errors.append(f"refractive_index ({config.refractive_index}) must be between 0.1 and 5.0")
        
        # Warnings for potentially problematic settings
        if config.advanced_filter and config.averaging == 'none':
            warnings.append("Advanced filter may not be effective without averaging")
        
        if config.dispersion_type == 'None' and config.dispersion_coefficient != 0:
            warnings.append("Dispersion coefficient is ignored when dispersion type is 'None'")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def parse_dispersion(self, dispersion_tuple: Tuple[str, str]) -> Tuple[str, int]:
        """
        Parse dispersion parameters from GUI tuple format.
        
        Args:
            dispersion_tuple: Tuple of (type, coefficient) as strings
            
        Returns:
            Tuple of (type, coefficient) with coefficient as int
            
        Raises:
            ValueError: If coefficient cannot be parsed as int
        """
        disp_type, coeff_str = dispersion_tuple
        
        # Validate type
        if disp_type not in self.VALID_OPTIONS['dispersion_type']:
            raise ValueError(f"Invalid dispersion type: {disp_type}. Must be one of {self.VALID_OPTIONS['dispersion_type']}")
        
        # Parse coefficient
        try:
            coefficient = int(coeff_str)
        except ValueError:
            raise ValueError(f"Invalid dispersion coefficient: {coeff_str}. Must be an integer.")
        
        # Validate range
        min_val, max_val = self.VALUE_RANGES['dispersion_coefficient']
        if not (min_val <= coefficient <= max_val):
            raise ValueError(f"Dispersion coefficient {coefficient} out of range [{min_val}, {max_val}]")
        
        return (disp_type, coefficient)
    
    def validate_slice_range(
        self,
        first_slice: int,
        last_slice: int,
        total_slices: int,
    ) -> ValidationResult:
        """
        Validate a slice range against total available slices.
        
        Args:
            first_slice: First slice number (1-indexed)
            last_slice: Last slice number (1-indexed)
            total_slices: Total number of slices available
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        if first_slice < 1:
            errors.append(f"first_slice ({first_slice}) must be >= 1")
        
        if last_slice < 1:
            errors.append(f"last_slice ({last_slice}) must be >= 1")
        
        if first_slice > last_slice:
            errors.append(f"first_slice ({first_slice}) must be <= last_slice ({last_slice})")
        
        if last_slice > total_slices:
            errors.append(f"last_slice ({last_slice}) exceeds total_slices ({total_slices})")
        
        if first_slice > total_slices:
            errors.append(f"first_slice ({first_slice}) exceeds total_slices ({total_slices})")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def calculate_num_slices(self, first_slice: int, last_slice: int) -> int:
        """
        Calculate the number of slices in a range.
        
        Args:
            first_slice: First slice number (1-indexed)
            last_slice: Last slice number (1-indexed)
            
        Returns:
            Number of slices in the range (inclusive)
        """
        return last_slice - first_slice + 1
    
    def calculate_equidistant_indices(
        self,
        first_slice: int,
        last_slice: int,
        num_slices: int,
    ) -> List[int]:
        """
        Calculate equidistant slice indices within a range.
        
        Args:
            first_slice: First slice number (1-indexed)
            last_slice: Last slice number (1-indexed)
            num_slices: Number of equidistant slices to calculate
            
        Returns:
            List of slice indices (1-indexed)
        """
        if num_slices <= 0:
            return []
        
        if num_slices == 1:
            return [(first_slice + last_slice) // 2]
        
        total_range = last_slice - first_slice
        if num_slices > total_range + 1:
            # More slices requested than available, return all
            return list(range(first_slice, last_slice + 1))
        
        step = total_range / (num_slices - 1)
        indices = [round(first_slice + i * step) for i in range(num_slices)]
        
        return indices
    
    def validate_db_range(self, db_min: int, db_max: int) -> ValidationResult:
        """
        Validate dynamic range (dB) values.
        
        Args:
            db_min: Minimum dB value
            db_max: Maximum dB value
            
        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors = []
        warnings = []
        
        min_range = self.VALUE_RANGES['db_min']
        max_range = self.VALUE_RANGES['db_max']
        
        if not (min_range[0] <= db_min <= min_range[1]):
            errors.append(f"db_min ({db_min}) must be between {min_range[0]} and {min_range[1]}")
        
        if not (max_range[0] <= db_max <= max_range[1]):
            errors.append(f"db_max ({db_max}) must be between {max_range[0]} and {max_range[1]}")
        
        if db_min >= db_max:
            errors.append(f"db_min ({db_min}) must be less than db_max ({db_max})")
        
        # Warnings for extreme values
        if db_max - db_min < 20:
            warnings.append("Narrow dynamic range may result in low contrast images")
        
        if db_max - db_min > 80:
            warnings.append("Wide dynamic range may result in washed out images")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def get_dispersion_recommendation(self, wavelength_nm: int) -> int:
        """
        Get recommended dispersion coefficient based on OCT wavelength.
        
        Args:
            wavelength_nm: OCT center wavelength in nanometers
            
        Returns:
            Recommended dispersion coefficient
        """
        if wavelength_nm >= 1400:
            # 1500nm OCT
            return -100
        elif wavelength_nm >= 1200:
            # 1310nm OCT
            return 20
        else:
            # Other wavelengths - default to 0
            return 0
    
    def merge_with_defaults(self, partial_config: Dict[str, Any]) -> SettingsConfig:
        """
        Merge a partial configuration with defaults.
        
        Args:
            partial_config: Dictionary with some settings
            
        Returns:
            Complete SettingsConfig with defaults for missing values
        """
        merged = {**self.DEFAULTS, **partial_config}
        return SettingsConfig(**merged)
