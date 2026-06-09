"""
CarlQuant Interpolation Service.

Pure, tkinter-free keyframe interpolation for coordinate configurations
(regions and AIR reference areas) across an image stack. Wraps the generic
interpolation engine and exposes it from the logic layer's stable import
location.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
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
