# -*- coding: utf-8 -*-
"""
CarlQuant Image Viewer Panel.

Interactive canvas viewer (extends BaseCanvasPanel) for OCT image stacks. Lets
the user define region boundaries (4-point) and AIR reference areas (2-point)
via click and drag. Renders analysis overlays via AnnotationRenderer.

Key contents:
- image_viewer_panel: Canvas viewer with region and AIR annotation tools.
- setup_specialized_bindings: Mouse bindings for region/AIR drawing modes.
- draw_specialized_overlays: Renders surfaces, depths, regions, and boundaries.
- save_region_config / save_air_config: Persists coordinates to the specimen config.
- Interpolation integration: Propagates keyframe coordinates across the stack.

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


import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from app.view.shared.tool_tip import Tooltip
from app.view.shared.error_handler import handle_errors
from app.view.shared.instruction_renderer import InstructionRenderer
from app.view.shared.metadata_prompt import ensure_metadata_set
from app.logic.carlquant import DataSaver
from app.logic.carlquant.interpolation import interpolate_region_coordinates, interpolate_air_coordinates
from app.logic.carlquant.annotation_colors import GROUND_TRUTH_MARK_COLOR
from app.logic.carlquant.ground_truth import (
    GroundTruthMismatchError,
    load_ground_truth,
    save_ground_truth,
)
from app.logic.carlquant.validation import interpolate_marks
from app.view.carlquant.annotation_renderer import (
    CoordinateConverter,
    SurfaceAnnotationRenderer,
    LesionDepthAnnotationRenderer,
    ExtractionRegionAnnotationRenderer,
    RegionBoundaryAnnotationRenderer,
    AIRAnnotationRenderer,
    RegionMarkerAnnotationRenderer
)
from app.view.shared.base_canvas_panel import BaseCanvasPanel


class image_viewer_panel(BaseCanvasPanel):
    """
    Interactive image viewer panel for OCT image stack visualization and annotation.
    
    This panel provides a canvas-based viewer with the following capabilities:
    - Display OCT image stacks with navigation controls
    - Zoom (Ctrl+MouseWheel) and pan (Ctrl+Drag) functionality
    - Define region boundaries via two-click selection
    - Define AIR reference area via drag selection (area containing actual air/empty space)
    - Automatic mode detection based on user interaction
    - Visual feedback for all configured regions and AIR reference areas
    
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
        
        # Initialize region/AIR reference-specific state BEFORE calling super().__init__()
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
        
        # AIR reference selection state
        self.air_drag_start = None         # Starting point for AIR reference drag
        self.air_drag_rectangle = None     # Canvas rectangle ID during drag
        self.air_visual_elements = []      # Visual elements for AIR reference display
        
        # A-Scan indicator state
        self.ascan_indicator_line = None   # Canvas line ID for A-scan column indicator
        self.ascan_indicator_column = None # Column it marks, so a redraw can restore it
        self.analysis_zoom_active = False  # True while this panel drives the zoom
        
        # A-Scan viewer callback (for synchronization)
        self.ascan_viewer_callback = None  # Callback to notify A-Scan viewer of slice changes

        # Validation mode state (ground-truth annotation of the true lesion end).
        # Off by default: this is a measurement tool and must never be able to
        # change a reported depth.
        self.validation_mode = False
        self.ground_truth_marks = {}        # {slice_index: [(x, y), ...]} image px
        self.ground_truth_dirty = False     # Unsaved marks pending for this specimen
        self.ground_truth_specimen_id = None  # Specimen the loaded marks belong to
        self.validation_changed_callback = None  # Notifies the results panel of edits

        # Initialize base class (sets up canvas, zoom, pan, navigation, etc.)
        super().__init__(context, "carl_image", canvas_bg='#505050')
    
    # ============================================================================
    # HOOK METHOD IMPLEMENTATIONS
    # ============================================================================
    
    def setup_specialized_bindings(self):
        """Setup region/AIR reference-specific mouse and keyboard bindings."""
        # Overlay toggle (use base class method) - just 'h' key
        # Only bind to canvas (gets focus on mouse enter via base class)
        self.canvas.bind("<h>", self.toggle_overlays)
        
        # Mouse bindings for region and AIR reference selection
        # Use add=True to preserve base class focus management
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_mouse_down, add=True)
        self.canvas.bind("<B1-Motion>", self.on_canvas_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_mouse_up)

        # Validation mode: right-click deletes a mark; 'u' undoes, 'c' clears.
        # Left-click marking is dispatched from the existing click handler rather
        # than a competing <ButtonPress-1> binding. Overlay hiding stays on 'h'.
        self.canvas.bind("<ButtonPress-3>", self.on_validation_right_click, add=True)
        self.canvas.bind("<u>", self.undo_last_ground_truth_mark)
        self.canvas.bind("<c>", self.clear_ground_truth_marks_on_slice)
    
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
        """Draw region boundaries and AIR reference areas after image rendering."""
        # Ground-truth marks are drawn before the overlay check: marking is done
        # with the detection overlay hidden ('h'), so the operator's own marks
        # have to stay visible in exactly that state.
        self.draw_ground_truth_marks()

        # Restore the A-scan column indicator. A full redraw rebuilds the
        # canvas, so without this the line vanishes whenever one happens --
        # most visibly on slider release, right after dragging.
        if self.ascan_indicator_column is not None:
            self.draw_ascan_indicator(self.ascan_indicator_column)

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
        
        # Draw region boundaries and AIR reference areas
        self.draw_region_boundaries(specimen, current_slice)
        self.draw_air_regions(specimen, current_slice)
        
        # Draw surface detection results
        self.draw_surface_results(specimen, current_slice)
        
        # Draw lesion depth results
        self.draw_lesion_depth(specimen, current_slice)
        
        # Draw extraction regions
        self.draw_extraction_regions(specimen, current_slice)

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

        # Flush ground-truth marks on slice change rather than on every click,
        # which would feel sluggish while marking.
        if self.last_displayed_slice is not None and self.last_displayed_slice != index:
            self.save_ground_truth_marks()

        # Picking up a specimen switch here keeps one specimen's marks from
        # being displayed -- or saved -- against another.
        self.sync_ground_truth_to_specimen()

        try:
            img_path = image_list[index]
            img = Image.open(img_path)

            self.rawImage = img.copy()
            self.zoom_level = 1.0
            self.image_offset_x = 0
            self.image_offset_y = 0
            
            # Update slider position BEFORE rendering (so overlays use correct slice)
            # Temporarily disable callback to prevent recursion
            self.scale.configure(command=lambda x: None)
            self.scale.set(index + 1)
            self.scale.configure(command=self.on_scale_change)
            
            self.scaleValue.set(f"Slice {index + 1} / {len(image_list)}")

            self.render_zoomed_image()  # Calls base class method which calls draw_specialized_overlays()
            
            # Update tracking
            self.last_displayed_slice = index
            self.current_slice_modified = False  # Reset for new slice
            
            # Notify A-Scan viewer if registered
            if self.ascan_viewer_callback is not None:
                img_width = self.rawImage.width
                img_height = self.rawImage.height
                self.ascan_viewer_callback(index, img_width, img_height)
            
            # Synchronize results panel row highlighting with current slice
            results_panel = self.context.get_panel("carl_results")
            if results_panel and hasattr(results_panel, 'sync_highlight_to_current_slice'):
                results_panel.sync_highlight_to_current_slice()
            
            # Give canvas focus so keyboard shortcuts work immediately
            self.canvas.focus_set()

        except Exception as e:
            if hasattr(self.context, 'status_bar') and self.context.status_bar:
                self.context.status_bar.update(f"Error displaying image {img_path}: {e}", level="error")




    # ============================================================================
    # MOUSE INTERACTION: AUTOMATIC MODE DETECTION (Click = Region, Drag = AIR Reference)
    # ============================================================================
    
    @handle_errors("imageViewerPanel.on_canvas_mouse_down")
    def on_canvas_mouse_down(self, event):
        """
        Handle mouse button press - start tracking for click vs drag detection.
        
        This is the entry point for the automatic mode detection system.
        The system determines whether the user is clicking (region selection)
        or dragging (AIR reference selection) based on mouse movement distance.
        
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
    # REGION BOUNDARY SELECTION (Four-Click Mode)
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
        # In validation mode a click marks the true lesion end instead of a
        # region boundary. Region selection is left untouched when it is off.
        if self.validation_mode:
            self.add_ground_truth_mark(event)
            return

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


    def _get_coordinate_converter(self):
        """
        Get a CoordinateConverter instance for current view state.
        
        Returns:
            CoordinateConverter instance or None if no image loaded
        """
        if not hasattr(self, 'rawImage') or self.rawImage is None:
            return None
        
        return CoordinateConverter(
            self.rawImage,
            self.zoom_level,
            self.image_offset_x,
            self.image_offset_y,
            getattr(self, 'fitted_width', self.rawImage.width),
            getattr(self, 'fitted_height', self.rawImage.height)
        )
    
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
        converter = self._get_coordinate_converter()
        if converter is None:
            return None, None
        
        return converter.canvas_to_image(canvas_x, canvas_y)


    def save_region_configuration(self, specimen, current_slice, 
                                 specimen_start, lesion_start, lesion_end, tooth_end):
        """
        Save region configuration with intelligent keyframe-based interpolation.
        
        Interpolation Logic:
        - First definition: propagate to all slices (initial setup)
        - Subsequent definitions: create keyframes and interpolate between them
        - Between keyframes: linear interpolation of all 4 boundary coordinates
        - Beyond last keyframe: use last keyframe value (constant extrapolation)
        
        Examples:
        1. Define slice 0 → all slices get same coordinates
        2. Define slice 0, then slice 9 → interpolate slices 1-8
        3. Define slice 0, 5, 9 → interpolate 1-4 and 6-8 independently
        
        Args:
            specimen: Specimen object to update
            current_slice: Current slice index (0-based)
            specimen_start: (x, y) tuple for specimen start
            lesion_start: (x, y) tuple for lesion start
            lesion_end: (x, y) tuple for lesion end
            tooth_end: (x, y) tuple for tooth end
        """
        def do_save():
            total_slices = len(specimen.images)
            
            # Initialize config if needed
            if not specimen.config:
                from app.logic.carlquant import SpecimenConfig
                specimen.config = SpecimenConfig(specimen_id=specimen.specimen_id)
            
            # Update current slice as keyframe (don't save yet - interpolation will save)
            DataSaver.update_specimen_region(
                specimen, current_slice,
                specimen_start, lesion_start, lesion_end, tooth_end,
                context=self.context,
                auto_save=False,  # Don't save yet - interpolation will save everything
                is_keyframe=True  # Mark as user-defined keyframe
            )
            
            # Perform interpolation between keyframes (saves at end)
            # This handles both first-time setup (1 keyframe → propagate) and multi-keyframe interpolation
            self._interpolate_region_coordinates(specimen, total_slices)
            
            # Determine status message based on number of user-defined keyframes
            num_keyframes = sum(1 for r in specimen.config.regions.values() if r.is_keyframe)
            if num_keyframes == 1:
                self.context.status_bar.update(
                    f"Region initialized for all {total_slices} slices (4 boundaries)", 
                    level="success"
                )
            else:
                self.context.status_bar.update(
                    f"Region keyframe set at slice {current_slice + 1}, interpolation applied", 
                    level="success"
                )

            # Update specimen panel display
            self.update_specimen_panel_display(specimen)
            
            # Refresh validation status to clear red highlighting if coordinates are now valid
            load_panel = self.context.get_panel("carl_load")
            if load_panel and hasattr(load_panel, 'refresh_validation_status'):
                load_panel.refresh_validation_status()
        
        # Ensure metadata is set before saving
        ensure_metadata_set(self.root, self.context, do_save)


    def _interpolate_region_coordinates(self, specimen, total_slices):
        """
        Interpolate region coordinates between keyframes using generic framework.
        
        Args:
            specimen: Specimen object with config.regions
            total_slices: Total number of slices in the stack
        """
        if not specimen.config or len(specimen.config.regions) == 0:
            return
        
        # Define update function for region configs
        def update_region(slice_idx, config, is_keyframe):
            DataSaver.update_specimen_region(
                specimen, slice_idx,
                config.specimen_start,
                config.lesion_start,
                config.lesion_end,
                config.tooth_end,
                context=self.context,
                auto_save=False,
                is_keyframe=is_keyframe
            )
        
        # Use generic interpolation framework
        interpolate_region_coordinates(
            specimen.config.regions,
            total_slices,
            update_region
        )
        
        # Save once after all interpolation is complete
        DataSaver.save_specimen_config(specimen)


    def update_specimen_panel_display(self, specimen):
        """
        Update the specimen panel to reflect new region configuration.
        
        This method is kept for compatibility but no longer updates display
        since REGIONS and AIR columns have been removed from the specimen panel.
        
        Args:
            specimen: Specimen object that was updated
        """
        # No-op: REGIONS and AIR columns removed from UI
        pass


    # ============================================================================
    # AIR (Air Reference) SELECTION (Drag Mode)
    # ============================================================================
    
    @handle_errors("imageViewerPanel.start_air_drag")
    def start_air_drag(self, event):
        """
        Start AIR reference rectangular selection when drag is detected.
        
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
        self.context.status_bar.update("Drawing AIR reference area...", level="info")


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
        Finalize AIR reference selection on mouse release.
        
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

        # Save AIR reference configuration with propagation logic
        point1 = (x1, y1)
        point2 = (x2, y2)
        self.save_air_configuration(specimen, current_slice, point1, point2)

        # Clear drag state
        self.air_drag_start = None
        if self.air_drag_rectangle:
            self.canvas.delete(self.air_drag_rectangle)
            self.air_drag_rectangle = None

        # Redraw AIR reference areas
        self.draw_air_regions(specimen, current_slice)


    def save_air_configuration(self, specimen, current_slice, point1, point2):
        """
        Save AIR reference configuration with intelligent keyframe-based interpolation.
        
        Interpolation Logic:
        - First definition: propagate to all slices (initial setup)
        - Subsequent definitions: create keyframes and interpolate between them
        - Between keyframes: linear interpolation of both corner points
        - Beyond last keyframe: use last keyframe value (constant extrapolation)
        
        This mirrors the region configuration logic for consistency.
        
        Args:
            specimen: Specimen object to update
            current_slice: Current slice index (0-based)
            point1: (x, y) tuple for top-left corner
            point2: (x, y) tuple for bottom-right corner
        """
        def do_save():
            total_slices = len(specimen.images)
            
            # Initialize config if needed
            if not specimen.config:
                from app.logic.carlquant import SpecimenConfig
                specimen.config = SpecimenConfig(specimen_id=specimen.specimen_id)
            
            # Update current slice as keyframe (don't save yet - interpolation will save)
            DataSaver.update_specimen_air(specimen, current_slice, point1, point2, context=self.context, auto_save=False, is_keyframe=True)
            
            # Perform interpolation between keyframes (saves at end)
            # This handles both first-time setup (1 keyframe → propagate) and multi-keyframe interpolation
            self._interpolate_air_coordinates(specimen, total_slices)
            
            # Determine status message based on number of user-defined keyframes
            num_keyframes = sum(1 for a in specimen.config.air.values() if a.is_keyframe)
            if num_keyframes == 1:
                self.context.status_bar.update(
                    f"AIR reference area initialized for all {total_slices} slices", 
                    level="success"
                )
            else:
                self.context.status_bar.update(
                    f"AIR reference keyframe set at slice {current_slice + 1}, interpolation applied", 
                    level="success"
                )
            
            # Refresh validation status to clear red highlighting if coordinates are now valid
            load_panel = self.context.get_panel("carl_load")
            if load_panel and hasattr(load_panel, 'refresh_validation_status'):
                load_panel.refresh_validation_status()
        
        # Ensure metadata is set before saving
        ensure_metadata_set(self.root, self.context, do_save)


    def _interpolate_air_coordinates(self, specimen, total_slices):
        """
        Interpolate AIR coordinates between keyframes using generic framework.
        
        Args:
            specimen: Specimen object with config.air
            total_slices: Total number of slices in the stack
        """
        if not specimen.config or len(specimen.config.air) == 0:
            return
        
        # Define update function for AIR configs
        def update_air(slice_idx, config, is_keyframe):
            DataSaver.update_specimen_air(
                specimen, slice_idx,
                config.point1,
                config.point2,
                context=self.context,
                auto_save=False,
                is_keyframe=is_keyframe
            )
        
        # Use generic interpolation framework
        interpolate_air_coordinates(
            specimen.config.air,
            total_slices,
            update_air
        )
        
        # Save once after all interpolation is complete
        DataSaver.save_specimen_config(specimen)


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

        converter = self._get_coordinate_converter()
        if converter is None:
            return
        
        renderer = AIRAnnotationRenderer(self.canvas, converter)
        renderer.draw(specimen.config.air[current_slice])


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
        
        converter = self._get_coordinate_converter()
        if converter is None:
            return
        
        renderer = RegionMarkerAnnotationRenderer(self.canvas, converter)
        renderer.draw(self.region_points)


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

        converter = self._get_coordinate_converter()
        if converter is None:
            return
        
        renderer = RegionBoundaryAnnotationRenderer(self.canvas, converter)
        renderer.draw(specimen.config.regions[current_slice])


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
        converter = self._get_coordinate_converter()
        if converter is None:
            return None
        
        return converter.image_to_canvas_rect(start_x, start_y, end_x, end_y)


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
        
        converter = self._get_coordinate_converter()
        if converter is None:
            return
        
        renderer = SurfaceAnnotationRenderer(self.canvas, converter)
        renderer.draw(surface)
    
    def draw_extraction_regions(self, specimen, current_slice):
        """
        Draw extraction regions (rotated rectangles with numbers).
        
        Args:
            specimen: Specimen object containing results
            current_slice: 0-based slice index
        """
        # Check if results exist for this slice
        if not hasattr(specimen, 'results') or current_slice not in specimen.results:
            return
        
        slice_result = specimen.results[current_slice]
        region_stats = slice_result.region_stats
        
        if not region_stats:
            return
        
        converter = self._get_coordinate_converter()
        if converter is None:
            return
        
        renderer = ExtractionRegionAnnotationRenderer(self.canvas, converter)
        renderer.draw(region_stats)
    
    def draw_lesion_depth(self, specimen, current_slice):
        """
        Draw lesion depth results (detected bottom of lesion).
        
        Synchronizes with A-Scan viewer checkboxes to show/hide component methods
        (knee point, inflection point, shoulder point) when the A-Scan viewer is open.
        
        Args:
            specimen: Specimen object containing results
            current_slice: 0-based slice index
        """
        # Check if results exist for this slice
        if not hasattr(specimen, 'results') or current_slice not in specimen.results:
            return
        
        slice_result = specimen.results[current_slice]
        lesion_depth = slice_result.lesion_depth
        
        if not lesion_depth or not lesion_depth.depth_points:
            return
        
        converter = self._get_coordinate_converter()
        if converter is None:
            return
        
        # Get checkbox states from A-Scan viewer if it's open
        show_knee = False
        show_inflection = False
        show_shoulder = False
        show_half_span = False

        # Check if there's an active A-Scan viewer with checkbox states
        results_panel = self.context.get_panel("carl_results")
        if results_panel and hasattr(results_panel, 'active_ascan_viewer'):
            ascan_viewer = results_panel.active_ascan_viewer
            if ascan_viewer and ascan_viewer.dialog and ascan_viewer.dialog.winfo_exists():
                # Get checkbox states from A-Scan viewer
                show_knee = ascan_viewer.show_knee_point.get()
                show_inflection = ascan_viewer.show_sigmoid_inflection.get()
                show_shoulder = ascan_viewer.show_sigmoid_shoulder.get()
                show_half_span = ascan_viewer.show_half_span.get()

        renderer = LesionDepthAnnotationRenderer(self.canvas, converter)
        renderer.draw(lesion_depth,
                     show_knee=show_knee,
                     show_inflection=show_inflection,
                     show_shoulder=show_shoulder,
                     show_half_span=show_half_span)

    # ============================================================================
    # VALIDATION MODE (GROUND-TRUTH ANNOTATION)
    # ============================================================================

    #: How close (image px) a right-click must be to delete a mark.
    GROUND_TRUTH_DELETE_RADIUS = 10

    @handle_errors("imageViewerPanel.set_validation_mode")
    def set_validation_mode(self, enabled):
        """Enable or disable ground-truth marking.

        Loads the specimen's existing marks on activation and flushes any
        pending ones on deactivation, so marks are never lost by toggling.
        """
        enabled = bool(enabled)
        if enabled == self.validation_mode:
            return

        self.validation_mode = enabled
        if enabled:
            self.load_ground_truth_marks()
            # Region selection is click-driven too; drop any half-finished one
            # so a stray boundary is not committed from a marking session.
            self.region_points = []
        else:
            self.save_ground_truth_marks()

        self.render_zoomed_image()

    @handle_errors("imageViewerPanel.load_ground_truth_marks")
    def load_ground_truth_marks(self):
        """Load the current specimen's operator marks from disk."""
        specimen = self._current_specimen()
        if specimen is None:
            self.ground_truth_marks = {}
            return

        try:
            self.ground_truth_marks = load_ground_truth(specimen)
        except GroundTruthMismatchError as error:
            # Marks recorded on another specimen would score as plausible
            # nonsense, so refuse them and say why rather than loading anyway.
            self.ground_truth_marks = {}
            if getattr(self.context, 'status_bar', None):
                self.context.status_bar.update(str(error), level="error")
        self.ground_truth_specimen_id = specimen.specimen_id
        self.ground_truth_dirty = False

    def sync_ground_truth_to_specimen(self):
        """Reload marks if the displayed specimen changed since they were loaded.

        Marks are absolute pixels into one image stack, so carrying them across
        a specimen switch would write one specimen's marks into another's file.
        """
        specimen = self._current_specimen()
        specimen_id = specimen.specimen_id if specimen is not None else None
        if specimen_id == self.ground_truth_specimen_id:
            return

        # Flush the outgoing specimen's marks before dropping them.
        self.save_ground_truth_marks()
        self.ground_truth_marks = {}
        self.ground_truth_specimen_id = specimen_id
        self.ground_truth_dirty = False
        if specimen is not None and self.validation_mode:
            self.load_ground_truth_marks()

    @handle_errors("imageViewerPanel.save_ground_truth_marks")
    def save_ground_truth_marks(self, force=False):
        """Write pending marks to disk.

        Saving happens on slice change, on leaving validation mode and on
        specimen close rather than on every click, which would be sluggish.
        """
        if not (self.ground_truth_dirty or force):
            return

        # Save against the specimen the marks were loaded from, not whatever is
        # displayed now: after a specimen switch those differ, and writing to
        # the wrong file would corrupt another specimen's ground truth.
        specimen_data = getattr(self.context, "specimen_data", {})
        specimen = specimen_data.get(self.ground_truth_specimen_id)
        if specimen is None:
            return

        save_ground_truth(specimen, self.ground_truth_marks)
        self.ground_truth_dirty = False

    def _current_specimen(self):
        """The Specimen currently displayed, or None."""
        specimen_id = getattr(self.context, "current_specimen_id", None)
        specimen_data = getattr(self.context, "specimen_data", {})
        if not specimen_id or specimen_id not in specimen_data:
            return None
        return specimen_data[specimen_id]

    def current_slice_index(self):
        """Zero-based index of the displayed slice."""
        return int(self.scale.get()) - 1

    def marks_on_current_slice(self):
        """Operator marks for the displayed slice."""
        return self.ground_truth_marks.get(self.current_slice_index(), [])

    def _after_marks_changed(self):
        """Redraw and notify the results panel after marks are edited."""
        self.ground_truth_dirty = True
        self.render_zoomed_image()
        if self.validation_changed_callback:
            self.validation_changed_callback()

    @handle_errors("imageViewerPanel.add_ground_truth_mark")
    def add_ground_truth_mark(self, event):
        """Add a mark at the clicked image coordinate."""
        image_x, image_y = self.canvas_to_image_coords(event.x, event.y)
        if image_x is None or image_y is None:
            return

        slice_index = self.current_slice_index()
        self.ground_truth_marks.setdefault(slice_index, []).append(
            (float(image_x), float(image_y)))
        self._after_marks_changed()

        if getattr(self.context, 'status_bar', None):
            count = len(self.ground_truth_marks[slice_index])
            self.context.status_bar.update(
                f"Mark {count} on slice {slice_index + 1}. "
                f"Right-click removes, 'u' undoes, 'c' clears.", level="info")

    @handle_errors("imageViewerPanel.on_validation_right_click")
    def on_validation_right_click(self, event):
        """Delete the nearest mark to the click, if one is close enough."""
        if not self.validation_mode:
            return

        image_x, image_y = self.canvas_to_image_coords(event.x, event.y)
        if image_x is None or image_y is None:
            return

        slice_index = self.current_slice_index()
        marks = self.ground_truth_marks.get(slice_index)
        if not marks:
            return

        distances = [((x - image_x) ** 2 + (y - image_y) ** 2) ** 0.5
                     for x, y in marks]
        nearest = min(range(len(marks)), key=distances.__getitem__)
        if distances[nearest] > self.GROUND_TRUTH_DELETE_RADIUS:
            return

        marks.pop(nearest)
        if not marks:
            del self.ground_truth_marks[slice_index]
        self._after_marks_changed()

    @handle_errors("imageViewerPanel.undo_last_ground_truth_mark")
    def undo_last_ground_truth_mark(self, event=None):
        """Remove the most recent mark on this slice."""
        if not self.validation_mode:
            return

        slice_index = self.current_slice_index()
        marks = self.ground_truth_marks.get(slice_index)
        if not marks:
            return

        marks.pop()
        if not marks:
            del self.ground_truth_marks[slice_index]
        self._after_marks_changed()

    @handle_errors("imageViewerPanel.clear_ground_truth_marks_on_slice")
    def clear_ground_truth_marks_on_slice(self, event=None):
        """Remove every mark on this slice."""
        if not self.validation_mode:
            return

        slice_index = self.current_slice_index()
        if slice_index not in self.ground_truth_marks:
            return

        del self.ground_truth_marks[slice_index]
        self._after_marks_changed()

    def should_show_ground_truth(self):
        """Whether ground truth belongs on the B-scan right now.

        Shown while marking, and also whenever the A-Scan viewer's "Ground
        Truth" toggle is on -- reading a disagreement means looking at the
        B-scan and the A-scan together, so the two views follow one another
        rather than requiring validation mode to be switched on as well.
        """
        if self.validation_mode:
            return True

        # Same lookup the per-method overlay toggles use (see draw_lesion_depth).
        results_panel = self.context.get_panel("carl_results")
        if not (results_panel and hasattr(results_panel, 'active_ascan_viewer')):
            return False

        ascan_viewer = results_panel.active_ascan_viewer
        if not (ascan_viewer and ascan_viewer.dialog
                and ascan_viewer.dialog.winfo_exists()):
            return False

        return bool(ascan_viewer.show_ground_truth.get())

    def draw_ground_truth_marks(self):
        """Draw the operator marks for the displayed slice, and the curve through them.

        Drawn regardless of ``overlays_visible``: marking is done with the
        detection overlay hidden so the marks stay independent of what the
        software reports, so the marks themselves must remain visible then.

        The marks are joined by the same interpolation the A-Scan viewer reads
        between them, so the two views show the same reference. The curve is
        display only and is clipped to the marked range.
        """
        if not self.should_show_ground_truth():
            return

        converter = self._get_coordinate_converter()
        if converter is None:
            return

        # A specimen opened without validation mode still needs its marks read.
        if not self.ground_truth_marks and self.ground_truth_specimen_id is None:
            self.load_ground_truth_marks()

        marks = self.marks_on_current_slice()
        if not marks:
            return

        self._draw_ground_truth_curve(converter, marks)

        size = 4
        for image_x, image_y in marks:
            canvas_x, canvas_y = converter.image_to_canvas(image_x, image_y)
            self.canvas.create_line(canvas_x - size, canvas_y - size,
                                    canvas_x + size, canvas_y + size,
                                    fill=GROUND_TRUTH_MARK_COLOR, width=2,
                                    tags="ground_truth")
            self.canvas.create_line(canvas_x - size, canvas_y + size,
                                    canvas_x + size, canvas_y - size,
                                    fill=GROUND_TRUTH_MARK_COLOR, width=2,
                                    tags="ground_truth")

    def _draw_ground_truth_curve(self, converter, marks):
        """Draw the interpolated curve joining the marks, under the markers."""
        curve = interpolate_marks(marks)
        if curve is None:
            return

        x_values, y_values = curve
        flattened = []
        for image_x, image_y in zip(x_values, y_values):
            canvas_x, canvas_y = converter.image_to_canvas(image_x, image_y)
            flattened.extend((canvas_x, canvas_y))

        if len(flattened) >= 4:
            self.canvas.create_line(*flattened, fill=GROUND_TRUTH_MARK_COLOR,
                                    width=1, tags="ground_truth")

    # ============================================================================
    # ZOOM TO ANALYSIS REGION
    # ============================================================================

    #: Padding into the sound enamel on each side of the lesion, in image px.
    ANALYSIS_ZOOM_PADDING = 40

    def lesion_region_bounds(self, specimen, current_slice):
        """Horizontal extent of the lesion on this slice, or None if unconfigured.

        Returns ``(x_start, x_end)`` in image pixels, padded into the sound
        enamel on both sides so the lesion is not framed edge to edge, and
        clamped to the image.
        """
        config = getattr(specimen, "config", None)
        if not config or current_slice not in getattr(config, "regions", {}):
            return None

        region = config.regions[current_slice]
        lesion_start = region.lesion_start[0]
        lesion_end = region.lesion_end[0]
        if lesion_end <= lesion_start:
            return None

        image_width = self.rawImage.width if self.rawImage is not None else lesion_end
        x_start = max(0, lesion_start - self.ANALYSIS_ZOOM_PADDING)
        x_end = min(image_width, lesion_end + self.ANALYSIS_ZOOM_PADDING)
        return x_start, x_end

    @handle_errors("imageViewerPanel.apply_analysis_zoom")
    def apply_analysis_zoom(self):
        """Frame the lesion region, mirroring the A-Scan viewer's zoom toggle.

        Zooms so the padded lesion region fills the canvas width and centres it.
        Returns True if a zoom was applied, False if the region is unknown --
        in which case the caller should leave the view alone rather than guess.
        """
        if self.rawImage is None:
            return False

        specimen = self._current_specimen()
        if specimen is None:
            return False

        bounds = self.lesion_region_bounds(specimen, self.current_slice_index())
        if bounds is None:
            return False

        x_start, x_end = bounds
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return False

        # Fit the region to the canvas width, but never below the fitted view
        # (1.0) or above the same ceiling the wheel zoom uses.
        region_width = x_end - x_start
        zoom = canvas_width / region_width
        fitted_zoom = canvas_width / self.rawImage.width
        zoom = max(fitted_zoom, min(zoom, 10.0))
        if zoom <= fitted_zoom:
            # The region is as wide as the image; the fitted view already shows it.
            return False

        self.zoom_level = zoom
        # Centre the region horizontally, and the image vertically.
        self.image_offset_x = -x_start * zoom + (canvas_width - region_width * zoom) / 2
        self.image_offset_y = (canvas_height - self.rawImage.height * zoom) / 2

        self.render_zoomed_image()
        return True

    @handle_errors("imageViewerPanel.reset_analysis_zoom")
    def reset_analysis_zoom(self):
        """Return to the fitted view after analysis zoom is switched off."""
        if self.rawImage is None:
            return

        self.zoom_level = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.render_zoomed_image()

    @handle_errors("imageViewerPanel.sync_analysis_zoom")
    def sync_analysis_zoom(self, enabled):
        """Apply or undo the analysis zoom to match the A-Scan viewer toggle."""
        if enabled:
            self.analysis_zoom_active = bool(self.apply_analysis_zoom())
        elif self.analysis_zoom_active:
            # Only undo a zoom this feature applied, so a manual zoom the
            # operator set themselves is not thrown away.
            self.analysis_zoom_active = False
            self.reset_analysis_zoom()

    def draw_ascan_indicator(self, column_x):
        """
        Draw a vertical line to indicate which A-scan column is being viewed.
        
        Args:
            column_x: X-coordinate (column index) in image space
        """
        # Clear previous indicator
        self.clear_ascan_indicator()

        # Remember the column so a full redraw can restore the line. Without
        # this the indicator survives dragging (which only redraws the line)
        # but disappears on release, when the canvas is rebuilt.
        self.ascan_indicator_column = column_x

        if not hasattr(self, 'rawImage') or self.rawImage is None:
            return

        converter = self._get_coordinate_converter()
        if converter is None:
            return

        # Convert image coordinates to canvas coordinates
        # Draw line from top to bottom of image
        image_height = self.rawImage.height
        canvas_coords = converter.image_to_canvas_rect(column_x, 0, column_x, image_height)
        
        if canvas_coords is None:
            return
        
        canvas_x1, canvas_y1, canvas_x2, canvas_y2 = canvas_coords
        
        # Draw vertical line in light purple
        self.ascan_indicator_line = self.canvas.create_line(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2,
            fill="#b19cd9",  # Light purple
            width=2,
            tags="ascan_indicator"
        )
    
    def clear_ascan_indicator(self):
        """Remove the indicator line from the canvas, keeping the column.

        The column is retained so a redraw can restore the line. Use
        :meth:`forget_ascan_indicator` when the A-Scan viewer closes and the
        indicator should not come back.
        """
        if self.ascan_indicator_line is not None:
            self.canvas.delete(self.ascan_indicator_line)
            self.ascan_indicator_line = None
        self.canvas.delete("ascan_indicator")

    def forget_ascan_indicator(self):
        """Clear the indicator and stop restoring it on redraw."""
        self.clear_ascan_indicator()
        self.ascan_indicator_column = None
    
    def register_ascan_viewer_callback(self, callback):
        """
        Register a callback to be notified when the slice changes.
        
        Args:
            callback: Function to call with (slice_index, image_width, image_height)
        """
        self.ascan_viewer_callback = callback
    
    def unregister_ascan_viewer_callback(self):
        """Unregister the A-Scan viewer callback."""
        self.ascan_viewer_callback = None
