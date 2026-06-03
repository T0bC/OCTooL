"""
CarlQuant Interpolation Service

Pure, tkinter-free keyframe interpolation for coordinate configurations
(regions and AIR reference areas) across an image stack.

Wraps the generic engine in ``app.logic.carlquant.interpolation`` and exposes it
from the logic layer's stable import location.
"""
from typing import Any, Callable, Dict

from app.logic.carlquant.interpolation import (
    CoordinateDescriptor,
    REGION_DESCRIPTOR,
    AIR_DESCRIPTOR,
    interpolate_coordinates,
    interpolate_region_coordinates,
    interpolate_air_coordinates,
)

__all__ = [
    "CoordinateDescriptor",
    "REGION_DESCRIPTOR",
    "AIR_DESCRIPTOR",
    "InterpolationService",
]


class InterpolationService:
    """Stateless service for keyframe-based coordinate interpolation."""

    @staticmethod
    def interpolate(
        config_dict: Dict[int, Any],
        total_slices: int,
        descriptor: CoordinateDescriptor,
        update_func: Callable[[int, Any, bool], None],
    ) -> None:
        """Interpolate any coordinate-based config dict using ``descriptor``."""
        interpolate_coordinates(config_dict, total_slices, descriptor, update_func)

    @staticmethod
    def interpolate_regions(
        config_dict: Dict[int, Any],
        total_slices: int,
        update_func: Callable[[int, Any, bool], None],
    ) -> None:
        """Interpolate region coordinates (4 points) across the stack."""
        interpolate_region_coordinates(config_dict, total_slices, update_func)

    @staticmethod
    def interpolate_air(
        config_dict: Dict[int, Any],
        total_slices: int,
        update_func: Callable[[int, Any, bool], None],
    ) -> None:
        """Interpolate AIR reference coordinates (2 points) across the stack."""
        interpolate_air_coordinates(config_dict, total_slices, update_func)
