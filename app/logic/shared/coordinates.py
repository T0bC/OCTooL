"""
Shared Coordinate Conversion.

Pure math (no tkinter) for converting between image and canvas coordinate
systems with zoom and pan. Shared by the AnnoLyze and CarlQuant canvas panels
and the CarlQuant annotation renderers.

Key contents:
- CoordinateConverter: Transforms image <-> canvas coordinates with zoom/pan.

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


class CoordinateConverter:
    """
    Handles conversion between image and canvas coordinate systems.

    This class encapsulates the logic for transforming coordinates based on
    zoom level and pan offset, making it reusable across all annotation types.
    """

    def __init__(
        self,
        raw_image,
        zoom_level,
        image_offset_x,
        image_offset_y,
        fitted_width=None,
        fitted_height=None,
    ):
        """
        Initialize coordinate converter.

        Args:
            raw_image: PIL Image object (the original image)
            zoom_level: Current zoom level (1.0 = fit to canvas)
            image_offset_x: X offset for panning
            image_offset_y: Y offset for panning
            fitted_width: Width when fitted to canvas (for zoom_level == 1.0)
            fitted_height: Height when fitted to canvas (for zoom_level == 1.0)
        """
        self.raw_image = raw_image
        self.zoom_level = zoom_level
        self.image_offset_x = image_offset_x
        self.image_offset_y = image_offset_y
        self.fitted_width = fitted_width or raw_image.width
        self.fitted_height = fitted_height or raw_image.height

        # Calculate current zoom factor
        if self.zoom_level == 1.0:
            self.current_zoom = self.fitted_width / self.raw_image.width
        else:
            self.current_zoom = self.zoom_level

    def image_to_canvas(self, image_x, image_y):
        """
        Convert single point from image to canvas coordinates.

        Args:
            image_x: X coordinate in image space
            image_y: Y coordinate in image space

        Returns:
            tuple: (canvas_x, canvas_y)
        """
        canvas_x = image_x * self.current_zoom + self.image_offset_x
        canvas_y = image_y * self.current_zoom + self.image_offset_y
        return canvas_x, canvas_y

    def image_to_canvas_rect(self, start_x, start_y, end_x, end_y):
        """
        Convert rectangle from image to canvas coordinates.

        Args:
            start_x: Start X coordinate in image space
            start_y: Start Y coordinate in image space
            end_x: End X coordinate in image space
            end_y: End Y coordinate in image space

        Returns:
            tuple: (canvas_start_x, canvas_start_y, canvas_end_x, canvas_end_y)
        """
        canvas_start_x = start_x * self.current_zoom + self.image_offset_x
        canvas_start_y = start_y * self.current_zoom + self.image_offset_y
        canvas_end_x = end_x * self.current_zoom + self.image_offset_x
        canvas_end_y = end_y * self.current_zoom + self.image_offset_y
        return canvas_start_x, canvas_start_y, canvas_end_x, canvas_end_y

    def canvas_to_image(self, canvas_x, canvas_y):
        """
        Convert canvas coordinates to image coordinates.

        Args:
            canvas_x: X coordinate on canvas
            canvas_y: Y coordinate on canvas

        Returns:
            tuple: (image_x, image_y) as integers, or (None, None) if out of bounds
        """
        # Convert to image-relative coordinates
        rel_x = (canvas_x - self.image_offset_x) / self.current_zoom
        rel_y = (canvas_y - self.image_offset_y) / self.current_zoom

        # Check if click is within image bounds
        if (
            rel_x < 0
            or rel_x >= self.raw_image.width
            or rel_y < 0
            or rel_y >= self.raw_image.height
        ):
            return None, None

        return int(rel_x), int(rel_y)

    def canvas_to_image_unclamped(self, canvas_x, canvas_y):
        """
        Convert canvas coordinates to image coordinates without bounds checking.

        Args:
            canvas_x: X coordinate on canvas
            canvas_y: Y coordinate on canvas

        Returns:
            tuple: (image_x, image_y) as floats; may be negative or exceed the
                   image size when the point lies outside the image
        """
        image_x = (canvas_x - self.image_offset_x) / self.current_zoom
        image_y = (canvas_y - self.image_offset_y) / self.current_zoom
        return image_x, image_y
