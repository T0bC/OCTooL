# -*- coding: utf-8 -*-
"""
Generic keyframe-based interpolation system for coordinate configurations.

This module provides a unified framework for interpolating coordinates between
user-defined keyframes across image stacks. It eliminates code duplication and
makes it easy to add new coordinate types.

Created on Oct 20, 2025
@author: Tobias Meissner
"""

from typing import Protocol, Dict, Tuple, Callable, List, Any, TypeVar
from dataclasses import dataclass


# ============================================================================
# PROTOCOLS - Define what makes a config "interpolatable"
# ============================================================================

class InterpolatableConfig(Protocol):
    """Protocol for configs that support keyframe interpolation.
    
    Any dataclass with these attributes can be interpolated:
    - slice_index: int - The slice this config belongs to
    - is_keyframe: bool - Whether this is a user-defined keyframe
    """
    slice_index: int
    is_keyframe: bool


# ============================================================================
# COORDINATE DESCRIPTORS - Define which fields to interpolate
# ============================================================================

@dataclass
class CoordinateDescriptor:
    """Describes which coordinate fields to interpolate for a config type.
    
    Attributes:
        field_names: List of field names containing (x, y) tuples to interpolate
        config_type_name: Human-readable name for status messages (e.g., "Region", "AIR")
    """
    field_names: List[str]
    config_type_name: str


# Pre-defined descriptors for existing config types
REGION_DESCRIPTOR = CoordinateDescriptor(
    field_names=["specimen_start", "lesion_start", "lesion_end", "tooth_end"],
    config_type_name="Region"
)

AIR_DESCRIPTOR = CoordinateDescriptor(
    field_names=["point1", "point2"],
    config_type_name="AIR"
)


# ============================================================================
# CORE INTERPOLATION ENGINE
# ============================================================================

ConfigType = TypeVar('ConfigType', bound=InterpolatableConfig)


def interpolate_coordinates(
    config_dict: Dict[int, ConfigType],
    total_slices: int,
    descriptor: CoordinateDescriptor,
    update_func: Callable[[int, ConfigType, bool], None]
) -> None:
    """
    Generic interpolation function for any coordinate-based configuration.
    
    Algorithm:
    1. Extract user-defined keyframes (is_keyframe=True)
    2. Single keyframe: Propagate to all slices
    3. Multiple keyframes: Interpolate between consecutive pairs
    4. Backfill: Apply first keyframe to slices before it
    5. Forward-fill: Apply last keyframe to slices after it
    
    Args:
        config_dict: Dictionary mapping slice_index -> config object
        total_slices: Total number of slices in the image stack
        descriptor: CoordinateDescriptor defining which fields to interpolate
        update_func: Function to update a slice with new config
                    Signature: (slice_idx: int, config: ConfigType, is_keyframe: bool) -> None
    
    Example:
        >>> def update_region(slice_idx, config, is_keyframe):
        ...     specimen.config.regions[slice_idx] = config
        >>> interpolate_coordinates(
        ...     specimen.config.regions,
        ...     total_slices=25,
        ...     descriptor=REGION_DESCRIPTOR,
        ...     update_func=update_region
        ... )
    """
    if not config_dict:
        return
    
    # Extract user-defined keyframes (ignore interpolated values)
    keyframes = sorted([idx for idx, cfg in config_dict.items() if cfg.is_keyframe])
    
    if len(keyframes) == 0:
        return  # No keyframes to interpolate from
    
    # Single keyframe: propagate to all slices
    if len(keyframes) == 1:
        _propagate_single_keyframe(
            keyframes[0], config_dict, total_slices, update_func
        )
        return
    
    # Multiple keyframes: interpolate between pairs
    _interpolate_between_keyframes(
        keyframes, config_dict, descriptor, update_func
    )
    
    # Backfill: slices before first keyframe
    _backfill_before_first_keyframe(
        keyframes[0], config_dict, update_func
    )
    
    # Forward-fill: slices after last keyframe
    _forward_fill_after_last_keyframe(
        keyframes[-1], config_dict, total_slices, update_func
    )


def _propagate_single_keyframe(
    keyframe_idx: int,
    config_dict: Dict[int, ConfigType],
    total_slices: int,
    update_func: Callable[[int, ConfigType, bool], None]
) -> None:
    """Propagate single keyframe to all other slices."""
    keyframe_config = config_dict[keyframe_idx]
    
    for slice_idx in range(total_slices):
        if slice_idx != keyframe_idx:
            update_func(slice_idx, keyframe_config, is_keyframe=False)


def _interpolate_between_keyframes(
    keyframes: List[int],
    config_dict: Dict[int, ConfigType],
    descriptor: CoordinateDescriptor,
    update_func: Callable[[int, ConfigType, bool], None]
) -> None:
    """Interpolate coordinates between consecutive keyframe pairs."""
    for i in range(len(keyframes) - 1):
        start_idx = keyframes[i]
        end_idx = keyframes[i + 1]
        
        # Skip if adjacent (no gap to interpolate)
        if end_idx - start_idx <= 1:
            continue
        
        start_config = config_dict[start_idx]
        end_config = config_dict[end_idx]
        
        # Interpolate each slice in the gap
        for slice_idx in range(start_idx + 1, end_idx):
            t = (slice_idx - start_idx) / (end_idx - start_idx)
            
            # Create interpolated config by copying start and updating coordinates
            interpolated_config = _create_interpolated_config(
                start_config, end_config, t, descriptor
            )
            
            update_func(slice_idx, interpolated_config, is_keyframe=False)


def _backfill_before_first_keyframe(
    first_keyframe_idx: int,
    config_dict: Dict[int, ConfigType],
    update_func: Callable[[int, ConfigType, bool], None]
) -> None:
    """Apply first keyframe to all slices before it."""
    if first_keyframe_idx > 0:
        first_config = config_dict[first_keyframe_idx]
        for slice_idx in range(first_keyframe_idx):
            update_func(slice_idx, first_config, is_keyframe=False)


def _forward_fill_after_last_keyframe(
    last_keyframe_idx: int,
    config_dict: Dict[int, ConfigType],
    total_slices: int,
    update_func: Callable[[int, ConfigType, bool], None]
) -> None:
    """Apply last keyframe to all slices after it."""
    if last_keyframe_idx < total_slices - 1:
        last_config = config_dict[last_keyframe_idx]
        for slice_idx in range(last_keyframe_idx + 1, total_slices):
            update_func(slice_idx, last_config, is_keyframe=False)


def _create_interpolated_config(
    start_config: ConfigType,
    end_config: ConfigType,
    t: float,
    descriptor: CoordinateDescriptor
) -> ConfigType:
    """
    Create a new config with interpolated coordinates.
    
    Args:
        start_config: Starting keyframe config
        end_config: Ending keyframe config
        t: Interpolation factor (0 to 1)
        descriptor: Defines which fields to interpolate
    
    Returns:
        New config object with interpolated coordinates
    """
    # Create a copy of start_config as a dict
    config_dict = {k: v for k, v in start_config.__dict__.items()}
    
    # Interpolate each coordinate field
    for field_name in descriptor.field_names:
        start_value = getattr(start_config, field_name, None)
        end_value = getattr(end_config, field_name, None)
        
        # Handle optional fields (e.g., point2 in AirConfig)
        if start_value is not None and end_value is not None:
            config_dict[field_name] = _lerp_point(start_value, end_value, t)
        elif start_value is not None:
            config_dict[field_name] = start_value
        else:
            config_dict[field_name] = None
    
    # Reconstruct config object from dict
    return type(start_config)(**config_dict)


def _lerp_point(start_point: Tuple[int, int], end_point: Tuple[int, int], t: float) -> Tuple[int, int]:
    """
    Linear interpolation between two (x, y) points.
    
    Args:
        start_point: Starting (x, y) coordinate
        end_point: Ending (x, y) coordinate
        t: Interpolation factor (0 = start, 1 = end)
    
    Returns:
        Interpolated (x, y) coordinate as integers
    """
    x = int(start_point[0] + (end_point[0] - start_point[0]) * t)
    y = int(start_point[1] + (end_point[1] - start_point[1]) * t)
    return (x, y)


# ============================================================================
# CONVENIENCE FUNCTIONS - Pre-configured for existing types
# ============================================================================

def interpolate_region_coordinates(
    config_dict: Dict[int, Any],
    total_slices: int,
    update_func: Callable[[int, Any, bool], None]
) -> None:
    """Convenience function for interpolating region coordinates (4 points)."""
    interpolate_coordinates(config_dict, total_slices, REGION_DESCRIPTOR, update_func)


def interpolate_air_coordinates(
    config_dict: Dict[int, Any],
    total_slices: int,
    update_func: Callable[[int, Any, bool], None]
) -> None:
    """Convenience function for interpolating AIR coordinates (2 points)."""
    interpolate_coordinates(config_dict, total_slices, AIR_DESCRIPTOR, update_func)
