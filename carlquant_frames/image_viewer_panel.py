# -*- coding: utf-8 -*-
"""
Image Viewer Panel for Carl Quant Analysis

This module provides an interactive image viewer for OCT image stacks with support for:
- Image navigation (arrow keys, mouse wheel, slider)
- Zoom and pan functionality
- Region boundary definition (two-click mode)
- AIR (Area of Interest Rectangle) selection (drag mode)
- Automatic mode detection: click = region boundary, drag = AIR selection
- Visual overlays for configured regions and AIR areas

Created on Mon Sep 29 15:46:17 2025
@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors
from utils.instruction_renderer import InstructionRenderer
from carlquant_frames.data_io import DataSaver
from base import BaseCanvasPanel


class image_viewer_panel(BaseCanvasPanel):
    """
    Interactive image viewer panel for OCT image stack visualization and annotation.
    
    This panel provides a canvas-based viewer with the following capabilities:
    - Display OCT image stacks with navigation controls
    - Zoom (Ctrl+MouseWheel) and pan (Ctrl+Drag) functionality
    - Define region boundaries via two-click selection
    - Define AIR regions via drag selection
    - Automatic mode detection based on user interaction
    - Visual feedback for all configured regions and AIR areas
    
    Attributes:
        context: Application context providing access to shared state
        canvas: Tkinter canvas for image display
        zoom_level: Current zoom level (1.0 = fit to canvas)
        slice_annotations: Dictionary of annotations per slice
        region_start_point: First click point for region selection
        air_drag_start: Starting point for AIR drag selection
    """
    @handle_errors("error in image_viewer_panel")
    def __init__(self, context):
        # Store reference to load frame before calling super()
        self.loadFrame = context.get_frame("carl_load")
        
        # Initialize region/AIR-specific state BEFORE calling super().__init__()
        # because setup_specialized_bindings() is called at the end of super().__init__()
        
        # Annotation state (for compatibility, though not heavily used in this panel)
        self.slice_annotations = {}
        self.current_annotation = None
        self.dragging_point_index = None
        self.point_handles = []
        self.overlay_handles = []
        
        # Drag detection state
        self.dragging_started = False
        self.hovered_point_index = None
        
        # Selection state - automatic mode detection
        self.region_points = []            # List of clicked points for region (4-click mode)
        self.region_visual_elements = []   # Visual elements for region display
        
        # Mouse interaction state
        self.mouse_down_pos = None         # Position where mouse was pressed
        self.is_dragging = False           # True if user is dragging (AIR mode)
        self.drag_threshold = 5            # Pixels to move before considering it a drag
        
        # AIR selection state
        self.air_drag_start = None         # Starting point for AIR drag
        self.air_drag_rectangle = None     # Canvas rectangle ID during drag
        self.air_visual_elements = []      # Visual elements for AIR display
        
        # Initialize base class (sets up canvas, zoom, pan, navigation, etc.)
        super().__init__(context, "carl_image", canvas_bg='#505050')
    
    # ============================================================================
    # HOOK METHOD IMPLEMENTATIONS
    # ============================================================================
    
    def setup_specialized_bindings(self):
        """Setup region/AIR-specific mouse and keyboard bindings."""
        # Overlay toggle (use base class method) - just 'h' key
        # Only bind to canvas (gets focus on mouse enter via base class)
        self.canvas.bind("<h>", self.toggle_overlays)
        
        # Mouse bindings for region and AIR selection
        # Use add=True to preserve base class focus management
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_mouse_down, add=True)
        self.canvas.bind("<B1-Motion>", self.on_canvas_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_mouse_up)
    
    def get_instruction_key(self):
        """Return instruction key for carlquant panel."""
        return 'carlquant_getting_started'
    
    def get_image_list(self):
        """Return the image list from current specimen."""
        specimen_id = getattr(self.context, "current_specimen_id", None)
        specimen_data = getattr(self.context, "specimen_data", {})
        
        if specimen_id and specimen_id in specimen_data:
            return specimen_data[specimen_id].images
        return []
    
    def get_image_path(self, index):
        """Return the path to the image at the given index."""
        image_list = self.get_image_list()
        if 0 <= index < len(image_list):
            return image_list[index]
        return None
    
    def draw_specialized_overlays(self):
        """Draw region boundaries and AIR regions after image rendering."""
        if not self.overlays_visible:
            return
        
        specimen_id = getattr(self.context, "current_specimen_id", None)
        if not specimen_id:
            return
        
        specimen_data = getattr(self.context, "specimen_data", {})
        if specimen_id not in specimen_data:
            return
        
        specimen = specimen_data[specimen_id]
        current_slice = int(self.scale.get()) - 1
        
        # Draw region boundaries and AIR regions
        self.draw_region_boundaries(specimen, current_slice)
        self.draw_air_regions(specimen, current_slice)
        
        # Draw surface detection results
        self.draw_surface_results(specimen, current_slice)

    # ============================================================================
    # IMAGE DISPLAY (OVERRIDE FOR SPECIMEN-SPECIFIC LOGIC)
    # ============================================================================
    
    @handle_errors("imageViewerPanel.display_image")
    def display_image(self, index=None):
        """
        Display an image from the current specimen's image stack.
        
        Overrides base class to handle specimen-specific image loading logic.
        
        Args:
            index: 0-based slice index. If None, uses current slider position.
        """
        self.canvas.delete("all")

        specimen_id = getattr(self.context, "current_specimen_id", None)
        specimen_data = getattr(self.context, "specimen_data", {})

        if not specimen_id or specimen_id not in specimen_data:
            if hasattr(self.context, 'status_bar') and self.context.status_bar:
                self.context.status_bar.update("No specimen selected.", level="warning")
            return

        image_list = specimen_data[specimen_id].images
        self.scale.configure(from_=1, to=len(image_list))

        if not image_list:
            if hasattr(self.context, 'status_bar') and self.context.status_bar:
                self.context.status_bar.update("No images found for selected specimen.", level="warning")
            return

        if index is None:
            index = int(self.scale.get() - 1)

        if index < 0 or index >= len(image_list):
            return
        
        # Auto-save previous slice if it has unsaved changes
        if (self.last_displayed_slice is not None and 
            self.last_displayed_slice != index and 
            self.current_slice_modified):
            self._auto_save_slice(self.last_displayed_slice)

        try:
            img_path = image_list[index]
            img = Image.open(img_path)

            self.rawImage = img.copy()
            self.zoom_level = 1.0
            self.image_offset_x = 0
            self.image_offset_y = 0

            self.render_zoomed_image()  # Calls base class method
            self.scaleValue.set(f"Slice {index + 1} / {len(image_list)}")
            
            # Update tracking
            self.last_displayed_slice = index
            self.current_slice_modified = False  # Reset for new slice
            
            # Give canvas focus so keyboard shortcuts work immediately
            self.canvas.focus_set()

        except Exception as e:
            if hasattr(self.context, 'status_bar') and self.context.status_bar:
                self.context.status_bar.update(f"Error displaying image {img_path}: {e}", level="error")
            else:
                print(f"Error displaying image {img_path}: {e}")




    # ============================================================================
    # MOUSE INTERACTION: AUTOMATIC MODE DETECTION (Click = Region, Drag = AIR)
    # ============================================================================
    
    @handle_errors("imageViewerPanel.on_canvas_mouse_down")
    def on_canvas_mouse_down(self, event):
        """
        Handle mouse button press - start tracking for click vs drag detection.
        
        This is the entry point for the automatic mode detection system.
        The system determines whether the user is clicking (region selection)
        or dragging (AIR selection) based on mouse movement distance.
        
        Args:
            event: Mouse button press event
        """
        # Skip if Ctrl is pressed (panning mode)
        if event.state & 0x0004:
            return

        # Store initial mouse position
        self.mouse_down_pos = (event.x, event.y)
        self.is_dragging = False


    @handle_errors("imageViewerPanel.on_canvas_mouse_drag")
    def on_canvas_mouse_drag(self, event):
        """
        Handle mouse drag - automatically switch to AIR mode if dragging detected.
        
        If the mouse moves beyond drag_threshold pixels, the interaction is
        classified as a drag and AIR selection mode is activated.
        
        Args:
            event: Mouse motion event
        """
        # Skip if Ctrl is pressed (panning mode)
        if event.state & 0x0004:
            return

        if self.mouse_down_pos is None:
            return

        # Calculate distance moved
        dx = event.x - self.mouse_down_pos[0]
        dy = event.y - self.mouse_down_pos[1]
        distance = (dx**2 + dy**2)**0.5

        # If moved beyond threshold, switch to drag mode (AIR selection)
        if not self.is_dragging and distance > self.drag_threshold:
            self.is_dragging = True
            self.start_air_drag(event)

        # Update AIR rectangle if dragging
        if self.is_dragging:
            self.update_air_drag(event)


    @handle_errors("imageViewerPanel.on_canvas_mouse_up")
    def on_canvas_mouse_up(self, event):
        """
        Handle mouse button release - finalize AIR or process region click.
        
        Determines whether the interaction was a click (region) or drag (AIR)
        and calls the appropriate handler.
        
        Args:
            event: Mouse button release event
        """
        # Skip if Ctrl is pressed (panning mode)
        if event.state & 0x0004:
            return

        if self.mouse_down_pos is None:
            return

        if self.is_dragging:
            # User was dragging - finalize AIR selection
            self.finish_air_selection(event)
        else:
            # User just clicked - handle region selection
            self.handle_region_click(event)

        # Reset state
        self.mouse_down_pos = None
        self.is_dragging = False


    # ============================================================================
    # REGION BOUNDARY SELECTION (Two-Click Mode)
    # ============================================================================
    
    @handle_errors("imageViewerPanel.handle_region_click")
    def handle_region_click(self, event):
        """
        Handle mouse clicks for region selection (4-click mode).
        
        Click 1: Specimen start (left boundary)
        Click 2: Lesion start
        Click 3: Lesion end
        Click 4: Tooth end (right boundary) - saves configuration
        
        Region boundaries are vertical lines used to define analysis regions.
        
        Args:
            event: Mouse button release event
        """
        # Get current specimen and slice
        specimen_id = getattr(self.context, "current_specimen_id", None)
        if not specimen_id:
            return

        specimen_data = getattr(self.context, "specimen_data", {})
        if specimen_id not in specimen_data:
            return

        specimen = specimen_data[specimen_id]
        current_slice = int(self.scale.get()) - 1  # Convert to 0-based index

        # Convert canvas coordinates to image coordinates
        image_x, image_y = self.canvas_to_image_coords(event.x, event.y)
        if image_x is None or image_y is None:
            return

        # Add point to list
        self.region_points.append((image_x, image_y))
        
        # Draw marker for this point
        self.draw_region_markers()
        
        # Update status message
        if len(self.region_points) < 4:
            self.context.status_bar.update(
                f"Point {len(self.region_points)}/4 set. Click 4 boundaries in any order.",
                level="info"
            )
        else:
            # All 4 points collected - sort by x-coordinate
            sorted_points = sorted(self.region_points, key=lambda p: p[0])
            
            # Assign based on position (leftmost to rightmost)
            specimen_start = sorted_points[0]   # Leftmost
            lesion_start = sorted_points[1]     # Second from left
            lesion_end = sorted_points[2]       # Third from left
            tooth_end = sorted_points[3]        # Rightmost
            
            self.save_region_configuration(
                specimen, current_slice,
                specimen_start, lesion_start, lesion_end, tooth_end
            )
            self.region_points = []  # Reset for next selection
            self.draw_region_boundaries(specimen, current_slice)


    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """
        Convert canvas coordinates to image coordinates.
        
        Takes into account current zoom level and pan offset. Returns None
        if the coordinates are outside the image bounds.
        
        Args:
            canvas_x: X coordinate on canvas
            canvas_y: Y coordinate on canvas
        
        Returns:
            tuple: (image_x, image_y) as integers, or (None, None) if out of bounds
        """
        if not hasattr(self, 'rawImage'):
            return None, None

        # Use fitted size if zoom_level == 1.0
        if self.zoom_level == 1.0:
            current_width = getattr(self, 'fitted_width', self.rawImage.width)
            current_height = getattr(self, 'fitted_height', self.rawImage.height)
            current_zoom = current_width / self.rawImage.width
        else:
            current_zoom = self.zoom_level

        # Convert to image-relative coordinates
        rel_x = (canvas_x - self.image_offset_x) / current_zoom
        rel_y = (canvas_y - self.image_offset_y) / current_zoom

        # Check if click is within image bounds
        if rel_x < 0 or rel_x >= self.rawImage.width or rel_y < 0 or rel_y >= self.rawImage.height:
            return None, None

        return int(rel_x), int(rel_y)


    def save_region_configuration(self, specimen, current_slice, 
                                 specimen_start, lesion_start, lesion_end, tooth_end):
        """
        Save region configuration with intelligent propagation logic.
        
        Propagation Logic:
        - If NO regions exist yet (first-time setup): propagate to all slices
        - If regions already exist: only update the current slice
        
        This allows users to set a global configuration initially, then
        fine-tune individual slices as needed.
        
        Args:
            specimen: Specimen object to update
            current_slice: Current slice index (0-based)
            specimen_start: (x, y) tuple for specimen start
            lesion_start: (x, y) tuple for lesion start
            lesion_end: (x, y) tuple for lesion end
            tooth_end: (x, y) tuple for tooth end
        """
        total_slices = len(specimen.images)
        
        # Check if any regions exist
        has_existing_regions = specimen.config and len(specimen.config.regions) > 0
        
        if not has_existing_regions:
            # First-time initialization: propagate to all slices
            for slice_idx in range(total_slices):
                DataSaver.update_specimen_region(
                    specimen, slice_idx, 
                    specimen_start, lesion_start, lesion_end, tooth_end
                )
            self.context.status_bar.update(
                f"Region initialized for all {total_slices} slices (4 boundaries)", 
                level="success"
            )
        else:
            # Regions already exist: only update current slice
            DataSaver.update_specimen_region(
                specimen, current_slice,
                specimen_start, lesion_start, lesion_end, tooth_end
            )
            self.context.status_bar.update(
                f"Region updated for slice {current_slice + 1} (4 boundaries)", 
                level="success"
            )

        # Update specimen panel display
        self.update_specimen_panel_display(specimen)


    def update_specimen_panel_display(self, specimen):
        """
        Update the specimen panel to reflect new region configuration.
        
        Updates the regions column in the specimen list to show the count
        of configured regions.
        
        Args:
            specimen: Specimen object that was updated
        """
        specimen_panel = self.context.get_panel("carl_specimen")
        if not specimen_panel:
            return

        # Find the row for this specimen
        for row_idx in range(specimen_panel.sheet.get_total_rows()):
            if specimen_panel.sheet.get_cell_data(row_idx, 0) == specimen.specimen_id:
                # Update regions column
                regions_count = len(specimen.config.regions) if specimen.config else 0
                regions_text = f"{regions_count} regions" if regions_count > 0 else ""
                specimen_panel.sheet.set_cell_data(row_idx, 2, regions_text)
                specimen.regions = regions_text
                break


    # ============================================================================
    # AIR (Area of Interest Rectangle) SELECTION (Drag Mode)
    # ============================================================================
    
    @handle_errors("imageViewerPanel.start_air_drag")
    def start_air_drag(self, event):
        """
        Start AIR rectangular selection when drag is detected.
        
        Stores both canvas and image coordinates of the drag start point.
        
        Args:
            event: Mouse motion event (when drag threshold exceeded)
        """
        # Get current specimen and slice
        specimen_id = getattr(self.context, "current_specimen_id", None)
        if not specimen_id:
            return

        specimen_data = getattr(self.context, "specimen_data", {})
        if specimen_id not in specimen_data:
            return

        # Use the original mouse_down_pos for start position
        start_x, start_y = self.mouse_down_pos
        
        # Convert canvas coordinates to image coordinates
        image_x, image_y = self.canvas_to_image_coords(start_x, start_y)
        if image_x is None or image_y is None:
            return

        # Store start point (both canvas and image coords)
        self.air_drag_start = {
            'canvas': (start_x, start_y),
            'image': (image_x, image_y)
        }
        self.context.status_bar.update("Drawing AIR region...", level="info")


    @handle_errors("imageViewerPanel.update_air_drag")
    def update_air_drag(self, event):
        """
        Update the visual rectangle as user drags.
        
        Draws a cyan rectangle from the drag start point to the current
        mouse position.
        
        Args:
            event: Mouse motion event
        """
        if self.air_drag_start is None:
            return

        # Remove previous rectangle
        if self.air_drag_rectangle is not None:
            self.canvas.delete(self.air_drag_rectangle)

        # Get start position
        start_canvas_x, start_canvas_y = self.air_drag_start['canvas']

        # Draw rectangle from start to current position
        self.air_drag_rectangle = self.canvas.create_rectangle(
            start_canvas_x, start_canvas_y, event.x, event.y,
            outline="cyan", width=2, tags="air_drag"
        )


    @handle_errors("imageViewerPanel.finish_air_selection")
    def finish_air_selection(self, event):
        """
        Finalize AIR selection on mouse release.
        
        Converts canvas coordinates to image coordinates, normalizes the
        rectangle (ensures top-left and bottom-right), and saves the
        configuration.
        
        Args:
            event: Mouse button release event
        """
        if self.air_drag_start is None:
            return

        # Get current specimen and slice
        specimen_id = getattr(self.context, "current_specimen_id", None)
        specimen_data = getattr(self.context, "specimen_data", {})
        
        if not specimen_id or specimen_id not in specimen_data:
            self.air_drag_start = None
            if self.air_drag_rectangle:
                self.canvas.delete(self.air_drag_rectangle)
                self.air_drag_rectangle = None
            return

        specimen = specimen_data[specimen_id]
        current_slice = int(self.scale.get()) - 1

        # Convert end position to image coordinates
        end_image_x, end_image_y = self.canvas_to_image_coords(event.x, event.y)
        if end_image_x is None or end_image_y is None:
            self.air_drag_start = None
            if self.air_drag_rectangle:
                self.canvas.delete(self.air_drag_rectangle)
                self.air_drag_rectangle = None
            return

        # Get start position
        start_image_x, start_image_y = self.air_drag_start['image']

        # Normalize coordinates (ensure top-left and bottom-right)
        x1 = min(start_image_x, end_image_x)
        y1 = min(start_image_y, end_image_y)
        x2 = max(start_image_x, end_image_x)
        y2 = max(start_image_y, end_image_y)

        # Save AIR configuration with propagation logic
        point1 = (x1, y1)
        point2 = (x2, y2)
        self.save_air_configuration(specimen, current_slice, point1, point2)

        # Clear drag state
        self.air_drag_start = None
        if self.air_drag_rectangle:
            self.canvas.delete(self.air_drag_rectangle)
            self.air_drag_rectangle = None

        # Redraw AIR regions
        self.draw_air_regions(specimen, current_slice)


    def save_air_configuration(self, specimen, current_slice, point1, point2):
        """
        Save AIR configuration with intelligent propagation logic.
        
        Propagation Logic:
        - If NO AIR regions exist yet (first-time setup): propagate to all slices
        - If AIR regions already exist: only update the current slice
        
        This mirrors the region configuration logic for consistency.
        
        Args:
            specimen: Specimen object to update
            current_slice: Current slice index (0-based)
            point1: (x, y) tuple for top-left corner
            point2: (x, y) tuple for bottom-right corner
        """
        total_slices = len(specimen.images)
        
        # Check if any AIR regions exist
        has_existing_air = specimen.config and len(specimen.config.air) > 0
        
        if not has_existing_air:
            # First-time initialization: propagate to all slices
            for slice_idx in range(total_slices):
                DataSaver.update_specimen_air(specimen, slice_idx, point1, point2)
            self.context.status_bar.update(
                f"AIR region initialized for all {total_slices} slices: ({point1[0]}, {point1[1]}) to ({point2[0]}, {point2[1]})", 
                level="success"
            )
        else:
            # AIR regions already exist: only update current slice
            DataSaver.update_specimen_air(specimen, current_slice, point1, point2)
            self.context.status_bar.update(
                f"AIR region updated for slice {current_slice + 1}: ({point1[0]}, {point1[1]}) to ({point2[0]}, {point2[1]})", 
                level="success"
            )


    # ============================================================================
    # VISUAL OVERLAY RENDERING
    # ============================================================================
    
    def draw_air_regions(self, specimen, current_slice):
        """
        Draw visual representation of AIR regions.
        
        Displays configured AIR regions as cyan rectangles on the canvas.
        
        Args:
            specimen: Specimen object containing AIR configuration
            current_slice: Current slice index (0-based)
        """
        self.clear_air_visuals()

        if not specimen.config or current_slice not in specimen.config.air:
            return

        air_config = specimen.config.air[current_slice]
        x1, y1 = air_config.point1
        x2, y2 = air_config.point2

        # Convert image coordinates to canvas coordinates
        canvas_coords = self.image_to_canvas_coords(x1, y1, x2, y2)
        if not canvas_coords:
            return

        canvas_x1, canvas_y1, canvas_x2, canvas_y2 = canvas_coords

        # Draw rectangle for AIR region
        rect = self.canvas.create_rectangle(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2,
            outline="cyan", width=2, tags="air_visual"
        )

        self.air_visual_elements.append(rect)


    def clear_air_visuals(self):
        """
        Clear all AIR visual elements from the canvas.
        """
        for element in self.air_visual_elements:
            self.canvas.delete(element)
        self.air_visual_elements.clear()
        self.canvas.delete("air_visual")
        self.canvas.delete("air_drag")


    def draw_region_markers(self):
        """
        Draw markers for all currently selected region points.
        
        Shows numbered circles for each clicked point during 4-point
        region boundary selection. Points are displayed in click order,
        but will be sorted by x-coordinate when saved.
        """
        self.clear_region_visuals()
        
        # Use cyan for temporary markers (will become green/yellow after sorting)
        color = "cyan"
        
        for i, (image_x, image_y) in enumerate(self.region_points):
            # Convert image coords to canvas coords for single point
            if not hasattr(self, 'rawImage'):
                continue
                
            if self.zoom_level == 1.0:
                current_width = getattr(self, 'fitted_width', self.rawImage.width)
                current_zoom = current_width / self.rawImage.width
            else:
                current_zoom = self.zoom_level
            
            canvas_x = image_x * current_zoom + self.image_offset_x
            canvas_y = image_y * current_zoom + self.image_offset_y
            
            # Draw circle
            marker = self.canvas.create_oval(
                canvas_x - 6, canvas_y - 6, canvas_x + 6, canvas_y + 6,
                fill=color, outline="white", width=2, tags="region_visual"
            )
            # Draw number label (click order)
            label = self.canvas.create_text(
                canvas_x, canvas_y,
                text=str(i + 1), fill="black", font=("Arial", 10, "bold"),
                tags="region_visual"
            )
            self.region_visual_elements.extend([marker, label])


    def draw_region_boundaries(self, specimen, current_slice):
        """
        Draw visual representation of region boundaries (4 vertical lines).
        
        Displays configured region boundaries as colored vertical lines
        spanning the full canvas height.
        
        Args:
            specimen: Specimen object containing region configuration
            current_slice: Current slice index (0-based)
        """
        self.clear_region_visuals()

        if not specimen.config or current_slice not in specimen.config.regions:
            return

        region = specimen.config.regions[current_slice]
        
        # Get all 4 boundary points with color scheme:
        # Green for specimen boundaries, Yellow for lesion boundaries
        points = [
            (region.specimen_start, "green", "Specimen Start"),
            (region.lesion_start, "yellow", "Lesion Start"),
            (region.lesion_end, "yellow", "Lesion End"),
            (region.tooth_end, "green", "Tooth End")
        ]
        
        canvas_height = self.canvas.winfo_height()
        
        for (point, color, label) in points:
            x, y = point
            
            # Convert image coordinates to canvas coordinates
            if not hasattr(self, 'rawImage'):
                continue
                
            if self.zoom_level == 1.0:
                current_width = getattr(self, 'fitted_width', self.rawImage.width)
                current_zoom = current_width / self.rawImage.width
            else:
                current_zoom = self.zoom_level
            
            canvas_x = x * current_zoom + self.image_offset_x
            
            # Draw vertical line
            line = self.canvas.create_line(
                canvas_x, 0, canvas_x, canvas_height,
                fill=color, width=2, tags="region_visual"
            )
            
            self.region_visual_elements.append(line)


    def image_to_canvas_coords(self, start_x, start_y, end_x, end_y):
        """
        Convert image coordinates to canvas coordinates.
        
        Takes into account current zoom level and pan offset. This is the
        inverse operation of canvas_to_image_coords.
        
        Args:
            start_x: Start X coordinate in image space
            start_y: Start Y coordinate in image space
            end_x: End X coordinate in image space
            end_y: End Y coordinate in image space
        
        Returns:
            tuple: (canvas_start_x, canvas_start_y, canvas_end_x, canvas_end_y)
                   or None if no image is loaded
        """
        if not hasattr(self, 'rawImage'):
            return None

        # Use fitted size if zoom_level == 1.0
        if self.zoom_level == 1.0:
            current_width = getattr(self, 'fitted_width', self.rawImage.width)
            current_height = getattr(self, 'fitted_height', self.rawImage.height)
            current_zoom = current_width / self.rawImage.width
        else:
            current_zoom = self.zoom_level

        canvas_start_x = start_x * current_zoom + self.image_offset_x
        canvas_start_y = start_y * current_zoom + self.image_offset_y
        canvas_end_x = end_x * current_zoom + self.image_offset_x
        canvas_end_y = end_y * current_zoom + self.image_offset_y

        return canvas_start_x, canvas_start_y, canvas_end_x, canvas_end_y


    def clear_region_visuals(self):
        """
        Clear all region visual elements from the canvas.
        """
        for element in self.region_visual_elements:
            self.canvas.delete(element)
        self.region_visual_elements.clear()
        self.canvas.delete("region_visual")


    def redraw_region_boundaries_after_zoom(self):
        """
        Redraw region boundaries after zoom/pan operations.
        
        Called automatically after zoom or pan to update visual overlays
        to match the new view transformation.
        """
        specimen_id = getattr(self.context, "current_specimen_id", None)
        if not specimen_id:
            return

        specimen_data = getattr(self.context, "specimen_data", {})
        if specimen_id not in specimen_data:
            return

        specimen = specimen_data[specimen_id]
        current_slice = int(self.scale.get()) - 1  # Convert to 0-based index
        self.draw_region_boundaries(specimen, current_slice)


    def redraw_air_regions_after_zoom(self):
        """
        Redraw AIR regions after zoom/pan operations.
        
        Called automatically after zoom or pan to update visual overlays
        to match the new view transformation.
        """
        specimen_id = getattr(self.context, "current_specimen_id", None)
        if not specimen_id:
            return

        specimen_data = getattr(self.context, "specimen_data", {})
        if specimen_id not in specimen_data:
            return

        specimen = specimen_data[specimen_id]
        current_slice = int(self.scale.get()) - 1  # Convert to 0-based index
        self.draw_air_regions(specimen, current_slice)
    
    
    def draw_surface_results(self, specimen, current_slice):
        """
        Draw surface detection results (peaks and fitted curve).
        
        Args:
            specimen: Specimen object containing results
            current_slice: 0-based slice index
        """
        # Check if results exist for this slice
        if not hasattr(specimen, 'results') or current_slice not in specimen.results:
            return
        
        slice_result = specimen.results[current_slice]
        surface = slice_result.surface
        
        if not surface:
            return
        
        # Get display options from context
        display_options = getattr(self.context, 'display_options', {})
        show_peaks = display_options.get('show_surface_peaks', tk.BooleanVar(value=True)).get()
        show_curve = display_options.get('show_fitted_curve', tk.BooleanVar(value=True)).get()
        
        # Draw fitted curve (orange, thicker line)
        if show_curve and surface.fitted_curves and "spline" in surface.fitted_curves:
            for x, y in surface.fitted_curves["spline"]:
                # Transform coordinates
                canvas_x, canvas_y = self.image_to_canvas(x, y)
                
                # Draw thicker line (3 pixels)
                for dy in range(-1, 2):
                    self.canvas.create_oval(
                        canvas_x - 1, canvas_y + dy - 1,
                        canvas_x + 1, canvas_y + dy + 1,
                        fill='orange', outline='orange',
                        tags="surface_overlay"
                    )
        
        # Draw surface peaks (green crosses)
        if show_peaks and surface.raw_points:
            for x, y in surface.raw_points:
                # Transform coordinates
                canvas_x, canvas_y = self.image_to_canvas(x, y)
                
                # Draw small cross (5x5 pixels)
                cross_size = 2
                self.canvas.create_line(
                    canvas_x - cross_size, canvas_y,
                    canvas_x + cross_size, canvas_y,
                    fill='green', width=2,
                    tags="surface_overlay"
                )
                self.canvas.create_line(
                    canvas_x, canvas_y - cross_size,
                    canvas_x, canvas_y + cross_size,
                    fill='green', width=2,
                    tags="surface_overlay"
                )
