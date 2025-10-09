# -*- coding: utf-8 -*-
"""
Annotation Renderer for Carl Quant Analysis

This module provides a structured approach to drawing annotations on the canvas.
It centralizes coordinate conversion logic and provides reusable drawing functions
for various annotation types.

Created on Thu Oct 09 2025
@author: Tobias Meissner
"""

import tkinter as tk


class CoordinateConverter:
    """
    Handles conversion between image and canvas coordinate systems.
    
    This class encapsulates the logic for transforming coordinates based on
    zoom level and pan offset, making it reusable across all annotation types.
    """
    
    def __init__(self, raw_image, zoom_level, image_offset_x, image_offset_y, 
                 fitted_width=None, fitted_height=None):
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
        if rel_x < 0 or rel_x >= self.raw_image.width or rel_y < 0 or rel_y >= self.raw_image.height:
            return None, None
        
        return int(rel_x), int(rel_y)


class BaseAnnotationRenderer:
    """
    Base class for annotation rendering.
    
    Provides common functionality for all annotation types including
    coordinate conversion and canvas drawing utilities.
    """
    
    def __init__(self, canvas, converter):
        """
        Initialize annotation renderer.
        
        Args:
            canvas: Tkinter canvas to draw on
            converter: CoordinateConverter instance
        """
        self.canvas = canvas
        self.converter = converter
    
    def draw_point(self, image_x, image_y, color="white", size=2, tags="annotation"):
        """
        Draw a single point (small circle) at image coordinates.
        
        Args:
            image_x: X coordinate in image space
            image_y: Y coordinate in image space
            color: Fill color
            size: Radius of the point
            tags: Canvas tags
        
        Returns:
            Canvas item ID
        """
        canvas_x, canvas_y = self.converter.image_to_canvas(image_x, image_y)
        return self.canvas.create_oval(
            canvas_x - size, canvas_y - size,
            canvas_x + size, canvas_y + size,
            fill=color, outline=color,
            tags=tags
        )
    
    def draw_line(self, points, color="white", width=2, tags="annotation"):
        """
        Draw a line connecting multiple points.
        
        Args:
            points: List of (x, y) tuples in image coordinates
            color: Line color
            width: Line width
            tags: Canvas tags
        
        Returns:
            List of canvas item IDs
        """
        if len(points) < 2:
            return []
        
        items = []
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            canvas_x1, canvas_y1 = self.converter.image_to_canvas(x1, y1)
            canvas_x2, canvas_y2 = self.converter.image_to_canvas(x2, y2)
            
            item = self.canvas.create_line(
                canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                fill=color, width=width,
                tags=tags
            )
            items.append(item)
        
        return items
    
    def draw_vertical_line(self, image_x, color="white", width=2, tags="annotation"):
        """
        Draw a vertical line spanning the full canvas height.
        
        Args:
            image_x: X coordinate in image space
            color: Line color
            width: Line width
            tags: Canvas tags
        
        Returns:
            Canvas item ID
        """
        canvas_x, _ = self.converter.image_to_canvas(image_x, 0)
        canvas_height = self.canvas.winfo_height()
        
        return self.canvas.create_line(
            canvas_x, 0, canvas_x, canvas_height,
            fill=color, width=width,
            tags=tags
        )
    
    def draw_rectangle(self, x1, y1, x2, y2, outline="white", width=2, tags="annotation"):
        """
        Draw a rectangle from image coordinates.
        
        Args:
            x1, y1: Top-left corner in image space
            x2, y2: Bottom-right corner in image space
            outline: Outline color
            width: Line width
            tags: Canvas tags
        
        Returns:
            Canvas item ID
        """
        canvas_x1, canvas_y1, canvas_x2, canvas_y2 = self.converter.image_to_canvas_rect(x1, y1, x2, y2)
        
        return self.canvas.create_rectangle(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2,
            outline=outline, width=width,
            tags=tags
        )
    
    def draw_polygon(self, corners, outline="white", width=2, tags="annotation"):
        """
        Draw a polygon from corner points.
        
        Args:
            corners: List of (x, y) tuples in image coordinates
            outline: Outline color
            width: Line width
            tags: Canvas tags
        
        Returns:
            List of canvas item IDs (one per edge)
        """
        items = []
        num_corners = len(corners)
        
        for i in range(num_corners):
            x1, y1 = corners[i]
            x2, y2 = corners[(i + 1) % num_corners]
            
            canvas_x1, canvas_y1 = self.converter.image_to_canvas(x1, y1)
            canvas_x2, canvas_y2 = self.converter.image_to_canvas(x2, y2)
            
            item = self.canvas.create_line(
                canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                fill=outline, width=width,
                tags=tags
            )
            items.append(item)
        
        return items
    
    def draw_text(self, image_x, image_y, text, color="white", font=("Arial", 12, "bold"), tags="annotation"):
        """
        Draw text at image coordinates.
        
        Args:
            image_x: X coordinate in image space
            image_y: Y coordinate in image space
            text: Text to display
            color: Text color
            font: Font tuple (family, size, style)
            tags: Canvas tags
        
        Returns:
            Canvas item ID
        """
        canvas_x, canvas_y = self.converter.image_to_canvas(image_x, image_y)
        
        return self.canvas.create_text(
            canvas_x, canvas_y,
            text=text, fill=color, font=font,
            tags=tags
        )
    
    def draw_cross(self, image_x, image_y, color="white", size=2, width=2, tags="annotation"):
        """
        Draw a cross marker at image coordinates.
        
        Args:
            image_x: X coordinate in image space
            image_y: Y coordinate in image space
            color: Cross color
            size: Half-size of the cross arms
            width: Line width
            tags: Canvas tags
        
        Returns:
            List of canvas item IDs (horizontal and vertical lines)
        """
        canvas_x, canvas_y = self.converter.image_to_canvas(image_x, image_y)
        
        items = []
        
        # Horizontal line
        h_line = self.canvas.create_line(
            canvas_x - size, canvas_y,
            canvas_x + size, canvas_y,
            fill=color, width=width,
            tags=tags
        )
        items.append(h_line)
        
        # Vertical line
        v_line = self.canvas.create_line(
            canvas_x, canvas_y - size,
            canvas_x, canvas_y + size,
            fill=color, width=width,
            tags=tags
        )
        items.append(v_line)
        
        return items


class SurfaceAnnotationRenderer(BaseAnnotationRenderer):
    """Renderer for surface detection results (peaks and fitted curves)."""
    
    def draw(self, surface, display_options):
        """
        Draw surface detection results.
        
        Args:
            surface: Surface detection result object
            display_options: Dictionary with display flags
        """
        if not surface:
            return
        
        show_peaks = display_options.get('show_surface_peaks', True)
        show_curve = display_options.get('show_fitted_curve', True)
        show_reference = display_options.get('show_reference_curve', True)
        
        # Draw reference curve (cyan, thin line) - bottom layer
        if show_reference and surface.fitted_curves and "reference" in surface.fitted_curves:
            for x, y in surface.fitted_curves["reference"]:
                self.draw_point(x, y, color='cyan', size=1, tags="surface_overlay")
        
        # Draw fitted curve (orange, thin line) - middle layer
        if show_curve and surface.fitted_curves and "spline" in surface.fitted_curves:
            for x, y in surface.fitted_curves["spline"]:
                self.draw_point(x, y, color='orange', size=1, tags="surface_overlay")
        
        # Draw surface peaks (green crosses) - top layer
        if show_peaks and surface.raw_points:
            for x, y in surface.raw_points:
                self.draw_cross(x, y, color='green', size=2, width=2, tags="surface_overlay")


class LesionDepthAnnotationRenderer(BaseAnnotationRenderer):
    """Renderer for lesion depth results."""
    
    def draw(self, lesion_depth):
        """
        Draw lesion depth results.
        
        Args:
            lesion_depth: Lesion depth result object
        """
        if not lesion_depth or not lesion_depth.depth_points:
            return
        
        points = lesion_depth.depth_points
        
        if len(points) > 1:
            # Draw line connecting all points
            self.draw_line(points, color='red', width=2, tags="lesion_depth_overlay")
            
            # Draw small circles at every 10th point for visibility
            for x, y in points[::10]:
                canvas_x, canvas_y = self.converter.image_to_canvas(x, y)
                self.canvas.create_oval(
                    canvas_x - 2, canvas_y - 2,
                    canvas_x + 2, canvas_y + 2,
                    fill='red', outline='darkred',
                    tags="lesion_depth_overlay"
                )


class ExtractionRegionAnnotationRenderer(BaseAnnotationRenderer):
    """Renderer for extraction regions (rotated rectangles with numbers)."""
    
    def draw(self, region_stats):
        """
        Draw extraction regions.
        
        Args:
            region_stats: List of region statistics objects
        """
        if not region_stats:
            return
        
        for stats in region_stats:
            if not stats.bounds or len(stats.bounds) == 0:
                continue
            
            # Choose color based on region type
            color = 'green' if stats.region_type == "sound" else 'red'
            
            # Check if we have rotated corners (4 points) or simple bbox (4 values)
            if len(stats.bounds) == 4 and isinstance(stats.bounds[0], tuple):
                # Rotated rectangle with 4 corner points
                self.draw_polygon(stats.bounds, outline=color, width=2, tags="extraction_regions")
                
                # Calculate center from corners for label
                canvas_corners = [self.converter.image_to_canvas(x, y) for x, y in stats.bounds]
                center_x = sum(x for x, y in canvas_corners) / 4
                center_y = sum(y for x, y in canvas_corners) / 4
                
            else:
                # Simple axis-aligned rectangle
                left_x, top_y, right_x, bottom_y = stats.bounds
                self.draw_rectangle(left_x, top_y, right_x, bottom_y, 
                                  outline=color, width=2, tags="extraction_regions")
                
                # Calculate center
                canvas_x1, canvas_y1 = self.converter.image_to_canvas(left_x, top_y)
                canvas_x2, canvas_y2 = self.converter.image_to_canvas(right_x, bottom_y)
                center_x = (canvas_x1 + canvas_x2) / 2
                center_y = (canvas_y1 + canvas_y2) / 2
            
            # Draw region number in center (use canvas coordinates directly)
            self.canvas.create_text(
                center_x, center_y,
                text=str(stats.region_index), fill=color,
                font=("Arial", 12, "bold"),
                tags="extraction_regions"
            )


class RegionBoundaryAnnotationRenderer(BaseAnnotationRenderer):
    """Renderer for region boundaries (4 vertical lines)."""
    
    def draw(self, region):
        """
        Draw region boundaries.
        
        Args:
            region: Region configuration object with boundary points
        """
        if not region:
            return
        
        # Define boundaries with color scheme:
        # Green for specimen boundaries, Yellow for lesion boundaries
        boundaries = [
            (region.specimen_start, "green", "Specimen Start"),
            (region.lesion_start, "yellow", "Lesion Start"),
            (region.lesion_end, "yellow", "Lesion End"),
            (region.tooth_end, "green", "Tooth End")
        ]
        
        for (point, color, label) in boundaries:
            x, y = point
            self.draw_vertical_line(x, color=color, width=2, tags="region_visual")


class AIRAnnotationRenderer(BaseAnnotationRenderer):
    """Renderer for AIR (Area of Interest Rectangle) regions."""
    
    def draw(self, air_config):
        """
        Draw AIR region.
        
        Args:
            air_config: AIR configuration object with point1 and point2
        """
        if not air_config:
            return
        
        x1, y1 = air_config.point1
        x2, y2 = air_config.point2
        
        self.draw_rectangle(x1, y1, x2, y2, outline="cyan", width=2, tags="air_visual")


class RegionMarkerAnnotationRenderer(BaseAnnotationRenderer):
    """Renderer for temporary region selection markers."""
    
    def draw(self, region_points):
        """
        Draw markers for region points during selection.
        
        Args:
            region_points: List of (x, y) tuples in image coordinates
        """
        color = "cyan"
        
        for i, (image_x, image_y) in enumerate(region_points):
            canvas_x, canvas_y = self.converter.image_to_canvas(image_x, image_y)
            
            # Draw circle
            self.canvas.create_oval(
                canvas_x - 6, canvas_y - 6, canvas_x + 6, canvas_y + 6,
                fill=color, outline="white", width=2, tags="region_visual"
            )
            
            # Draw number label (click order)
            self.canvas.create_text(
                canvas_x, canvas_y,
                text=str(i + 1), fill="black", font=("Arial", 10, "bold"),
                tags="region_visual"
            )
