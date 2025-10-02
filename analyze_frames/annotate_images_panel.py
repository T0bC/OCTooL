# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 11:13:52 2025

@author: meissnerto
"""

import tkinter as tk
from tkinter import ttk
from utils.tool_tip import Tooltip
from PIL import Image, ImageTk, ImageDraw
from utils.error_handler import handle_errors
from utils.instruction_renderer import InstructionRenderer
import numpy as np
from scipy.interpolate import splprep, splev
from pathlib import Path
import json
from datetime import datetime
from base import BaseCanvasPanel

class annotatePanel(BaseCanvasPanel):
    @handle_errors("error in annotatePanel")
    def __init__(self, context):
        # Store reference to load frame before calling super()
        self.loadFrame = context.get_frame("load")
        
        # Initialize annotation-specific state BEFORE calling super().__init__()
        # because setup_specialized_bindings() is called at the end of super().__init__()
        self.slice_annotations = {}
        self.current_annotation = None
        self.dragging_point_index = None
        self.point_handles = []
        self.overlay_handles = []  # for non drawn overlays for boolean, categorial data types
        
        # Drag an existing point check
        self.dragging_started = False
        self.hovered_point_index = None  # used for hover detection
        
        # Initialize base class (sets up canvas, zoom, pan, navigation, etc.)
        super().__init__(context, "image", canvas_bg='#505050')
    
    # ============================================================================
    # HOOK METHOD IMPLEMENTATIONS
    # ============================================================================
    
    def setup_specialized_bindings(self):
        """Setup annotation-specific mouse and keyboard bindings."""
        # Annotation toggle (use base class method) - just 'h' key
        # Only bind to canvas (gets focus on mouse enter via base class)
        self.canvas.bind("<h>", self.toggle_overlays)
        
        # Mouse bindings for annotation
        # Use add=True to preserve base class focus management
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start, add=True)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)
        self.canvas.bind("<Motion>", self.on_mouse_motion)
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # Curve fitting
        self.window.bind("<KeyPress-f>", self.fit_bezier_curve)
    
    def get_instruction_key(self):
        """Return instruction key for analyze panel."""
        return 'analyze_getting_started'
    
    def get_image_list(self):
        """Return the image list from context."""
        return getattr(self.context, "image_list", [])
    
    def draw_specialized_overlays(self):
        """Draw annotations and overlays after image rendering."""
        # Always draw annotations (draw_annotation handles visibility internally)
        self.draw_annotation()
        
        # Only draw non-drawn overlays (boolean, categorical) if visible
        if self.overlays_visible:
            self.draw_overlay_annotations()

    # ============================================================================
    # IMAGE ANNOTATION FUNCTIONS
    # ============================================================================
    @handle_errors("annotatePanel.on_canvas_click")
    def on_canvas_click(self, event):
        if not hasattr(self, 'rawImage') or self.rawImage is None or not hasattr(self, 'fitted_width'):
            return None  # Prevent crash
        if self.dragging_started:
            return  # Skip adding point if drag was initiated

        x, y = event.x, event.y
        img_coords = self.canvas_to_image_coords(x, y)
        if img_coords is None or img_coords == (None, None):
            return
        
        img_x, img_y = img_coords

        if not (0 <= img_x < self.rawImage.width and 0 <= img_y < self.rawImage.height):
            return

        if self.current_annotation is None:
            self.current_annotation = {
                "id": None,
                "points": [],
                "mode": "line",
                "locked": False
            }

        self.current_annotation["points"].append((img_x, img_y))
        self.draw_annotation()

    @handle_errors("annotatePanel.draw_annotation")
    def draw_annotation(self):
        self.canvas.delete("annotation")
        self.point_handles.clear()

        index = int(self.scale.get()) - 1

        # Build list of annotations to draw
        annotations = []
        
        # Only include committed annotations if overlays are visible
        if self.overlays_visible:
            annotations = self.slice_annotations.get(index, [])
        
        # Always include current annotation being edited (even if overlays are hidden)
        if self.current_annotation:
            annotations = annotations + [self.current_annotation]

        for ann in annotations:
            pts = ann["points"]
            mode = ann["mode"]
            locked = ann["locked"]
            color = ann.get("color", "#ffffb2")

            canvas_pts = [self.image_to_canvas_coords(x, y) for x, y in pts]

            # Always draw the line/curve
            if len(canvas_pts) >= 2:
                if mode == "line":
                    for i in range(len(canvas_pts)-1):
                        self.canvas.create_line(*canvas_pts[i], *canvas_pts[i+1],
                                                fill=color,
                                                width=2,
                                                tags="annotation")
                else:
                    # Spline mode: requires at least 4 points for cubic spline
                    # Fall back to line drawing if not enough points
                    if len(canvas_pts) < 4:
                        # Draw as lines with visual feedback that spline needs more points
                        for i in range(len(canvas_pts)-1):
                            self.canvas.create_line(*canvas_pts[i], *canvas_pts[i+1],
                                                    fill=color,
                                                    width=2,
                                                    dash=(4, 2),  # Dashed line to indicate "waiting for spline"
                                                    tags="annotation")
                    else:
                        try:
                            pts_np = np.array(canvas_pts)
                            # Use cubic spline (k=3) which requires at least 4 points
                            tck, _ = splprep([pts_np[:,0], pts_np[:,1]], s=0, k=3)
                            u = np.linspace(0, 1, 500)
                            x_new, y_new = splev(u, tck)
                            for i in range(len(x_new)-1):
                                self.canvas.create_line(x_new[i], y_new[i], x_new[i+1], y_new[i+1],
                                                        fill=color,
                                                        width=2,
                                                        tags="annotation")
                        except Exception as e:
                            # If spline fails, fall back to line drawing
                            for i in range(len(canvas_pts)-1):
                                self.canvas.create_line(*canvas_pts[i], *canvas_pts[i+1],
                                                        fill=color,
                                                        width=2,
                                                        tags="annotation")

            # Only draw point handles if annotation is editable
            if not locked:
                for x, y in canvas_pts:
                    handle = self.canvas.create_oval(x-3, y-3, x+3, y+3,
                                                     fill=color,
                                                     outline="#ffff00",
                                                     width=2,
                                                     tags="annotation")
                    self.point_handles.append(handle)

    @handle_errors("annotatePanel.get_annotation_length")
    def get_annotation_length(self, slice_index):
        # Use current annotation if it's active
        if self.current_annotation and len(self.current_annotation["points"]) >= 2:
            points = self.current_annotation["points"]
            mode = self.current_annotation["mode"]
        else:
            # Otherwise, use the last committed annotation for this slice
            annotations = self.slice_annotations.get(slice_index, [])
            if not annotations:
                return 0.0
            last_ann = annotations[-1]
            points = last_ann["points"]
            mode = last_ann["mode"]

        if len(points) < 2:
            return 0.0

        pts = np.array(points)
        if mode == "line":
            diffs = np.diff(pts, axis=0)
            length = np.sum(np.sqrt(np.sum(diffs**2, axis=1)))
        else:
            # Spline mode: requires at least 4 points for cubic spline
            if len(points) < 4:
                # Fall back to line length calculation if not enough points
                diffs = np.diff(pts, axis=0)
                length = np.sum(np.sqrt(np.sum(diffs**2, axis=1)))
            else:
                try:
                    tck, _ = splprep([pts[:, 0], pts[:, 1]], s=0, k=3)
                    u = np.linspace(0, 1, 1000)
                    x_new, y_new = splev(u, tck)
                    length = np.sum(np.sqrt(np.diff(x_new)**2 + np.diff(y_new)**2))
                except Exception:
                    # Fall back to line length if spline fails
                    diffs = np.diff(pts, axis=0)
                    length = np.sum(np.sqrt(np.sum(diffs**2, axis=1)))

        return length

    @handle_errors("annotatePanel.commit_annotation")
    def commit_annotation(self, label, color="#FFFFFF"):
        index = int(self.scale.get()) - 1
        if self.current_annotation and len(self.current_annotation["points"]) >= 2:
            self.current_annotation["id"] = f"{label}_{len(self.slice_annotations.get(index, []))}"
            self.current_annotation["feature"] = label
            self.current_annotation["color"] = color
            self.current_annotation["locked"] = True

            if index not in self.slice_annotations:
                self.slice_annotations[index] = []

            self.slice_annotations[index].append(self.current_annotation)
            committed_id = self.current_annotation["id"]
            self.current_annotation = None
            
            # Mark this slice as modified for auto-save on navigation
            self.mark_slice_modified()
            
            # Flash annotation will show the committed annotation briefly, then hide it
            self.flash_annotation()
            return committed_id
        return None

    @handle_errors("annotatePanel.draw_overlay_annotations")
    def draw_overlay_annotations(self):
        """
        draws non continous annotations to the image. It automatically gets for
        which slice we have data types that are not drawn and displays those
        on the image.

        Returns
        -------
        None.

        """
        slice_index = int(self.scale.get()) - 1
        # Clear previous overlays
        for handle in self.overlay_handles:
            self.canvas.delete(handle)
        self.overlay_handles.clear()

        results_panel = self.context.get_panel("results")
        if not results_panel:
            return

        headers = results_panel.sheet.headers()
        sheet = results_panel.sheet
        total_rows = sheet.total_rows()

        # Early exit if sheet is empty or slice index is out of bounds
        if total_rows == 0 or slice_index >= total_rows:
            return

        row_data = sheet.get_row_data(slice_index)
        if row_data is None:
            return

        non_drawn_types = ["Boolean", "Categorical", "Ordinal", "Text/String"]
        add_columns_panel = self.context.get_panel("add_columns")
        if not add_columns_panel:
            return

        # Starting position inside image bounds (image coordinates)
        img_x = 10
        img_y_start = 10
        spacing = 20  # vertical spacing in image pixels

        canvas_x, canvas_y = self.image_to_canvas_coords(img_x, img_y_start)

        # Track bounding box
        max_width = 0
        label_positions = []

        for col_index, col_name in enumerate(headers):
            value = row_data[col_index]
            if not value:
                continue

            data_type = add_columns_panel.column_data_types.get(col_name, "")
            if data_type not in non_drawn_types:
                continue

            color = add_columns_panel.column_colors.get(col_name, "#FFFFFF")
            text = f"{col_name}: {value}"

            # Convert image coordinates to canvas coordinates
            label_x, label_y = self.image_to_canvas_coords(img_x, img_y_start)

            # Create text temporarily to measure its width
            temp_id = self.canvas.create_text(
                label_x, label_y,
                text=text,
                anchor="nw",
                font=("Helvetica", 10)
            )
            bbox = self.canvas.bbox(temp_id)
            self.canvas.delete(temp_id)

            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            max_width = max(max_width, text_width)

            label_positions.append((label_x, label_y, text, color))
            img_y_start += spacing

        # Draw all labels
        for label_x, label_y, text, color in label_positions:
            text_id = self.canvas.create_text(
                label_x, label_y,
                text=text,
                anchor="nw",
                fill=color,
                font=("Helvetica", 10),
                tags="annotation"
            )
            self.overlay_handles.append(text_id)

    @handle_errors("annotatePanel.flash_annotation")
    def flash_annotation(self, duration=800):
        self.overlays_visible = True
        self.draw_annotation()
        self.draw_overlay_annotations()

        # Schedule hiding after duration
        self.window.after(duration, self._hide_annotations_if_not_toggled)

    @handle_errors("annotatePanel._hide_annotations_if_not_toggled")
    def _hide_annotations_if_not_toggled(self):
        # Only hide if user hasn't manually toggled visibility back on
        # This auto-hide only triggers if overlays are still visible after the flash duration
        if self.overlays_visible:
            self.overlays_visible = False
            # Trigger a full redraw to properly clear overlays
            if self.rawImage is not None:
                self.render_zoomed_image()

    # ============================================================================
    # CURVE FITTING
    # ============================================================================
    @handle_errors("annotatePanel.fit_bezier_curve")
    def fit_bezier_curve(self, event=None):
        if not self.current_annotation or len(self.current_annotation["points"]) < 2:
            return

        # Toggle mode for the current annotation only
        current_mode = self.current_annotation["mode"]
        num_points = len(self.current_annotation["points"])
        
        if current_mode == "line":
            # Switching to spline mode
            if num_points < 4:
                # Show user feedback about minimum points needed
                if hasattr(self.context, 'status_bar') and self.context.status_bar:
                    self.context.status_bar.update(
                        f"Spline mode activated. Add {4 - num_points} more point(s) for smooth curve (currently {num_points}/4)",
                        level="info"
                    )
            self.current_annotation["mode"] = "spline"
        else:
            # Switching back to line mode
            self.current_annotation["mode"] = "line"
            if hasattr(self.context, 'status_bar') and self.context.status_bar:
                self.context.status_bar.update("Line mode activated", level="info")
        
        self.draw_annotation()

    # %% drag existing points to new position

    @handle_errors("annotatePanel.create_new_point")
    def create_new_point(self, event):
        """Create a new annotation point"""
        # Early return if no image is loaded
        if self.rawImage is None:
            return
        
        x, y = event.x, event.y

        img_coords = self.canvas_to_image_coords(x, y)
        if img_coords is None or img_coords == (None, None):
            return

        img_x, img_y = img_coords

        if not (0 <= img_x < self.rawImage.width and 0 <= img_y < self.rawImage.height):
            return

        if self.current_annotation is None:
            self.current_annotation = {
                "id": None,
                "points": [],
                "mode": "line",
                "locked": False
            }

        self.current_annotation["points"].append((img_x, img_y))
        self.draw_annotation()

    @handle_errors("annotatePanel.on_drag_motion")
    def on_drag_motion(self, event):
        """Handle mouse drag - move point if one is selected"""
        if self.dragging_point_index is not None:
            # Early return if no image is loaded
            if self.rawImage is None:
                return
            
            self.dragging_started = True

            img_coords = self.canvas_to_image_coords(event.x, event.y)
            if img_coords is None or img_coords == (None, None):
                return
            
            img_x, img_y = img_coords

            # Constrain to image bounds
            if not (0 <= img_x < self.rawImage.width and 0 <= img_y < self.rawImage.height):
                return

            # Update point in current annotation
            if self.current_annotation and self.dragging_point_index < len(self.current_annotation["points"]):
                self.current_annotation["points"][self.dragging_point_index] = (img_x, img_y)
                self.draw_annotation()
        else:
            # Handle hover effects when not dragging
            self.handle_hover_effects(event.x, event.y)

    @handle_errors("annotatePanel.on_drag_start")
    def on_drag_start(self, event):
        """Handle mouse press - check if clicking on existing point or starting new point"""
        self.dragging_started = False
        self.dragging_point_index = None

        # Check if clicking near an existing point (with larger hit area)
        point_index = self.get_point_near_cursor(event.x, event.y)
        if point_index is not None:
            self.dragging_point_index = point_index
            self.dragging_started = True
            # Highlight selected point for dragging (white)
            handle = self.point_handles[point_index]
            self.canvas.itemconfig(handle, outline="white", width=2)
            return  # Exit early - we found a point to drag

    @handle_errors("annotatePanel.on_drag_end")
    def on_drag_end(self, event):
        """Handle mouse release - end drag or create new point"""
        if self.dragging_point_index is not None:
            # Reset drag highlight and restore normal/hover state
            if self.dragging_point_index < len(self.point_handles):
                handle = self.point_handles[self.dragging_point_index]
                # Check if still hovering over the point
                if self.get_point_near_cursor(event.x, event.y) == self.dragging_point_index:
                    self.canvas.itemconfig(handle, outline="green", width=2)
                else:
                    self.canvas.itemconfig(handle, outline="red", width=1)
            self.dragging_point_index = None
        elif not self.dragging_started:
            # No point was being dragged, so create a new point
            self.create_new_point(event)

        self.dragging_started = False

# %% hover over point logic
    @handle_errors("annotatePanel.get_point_near_cursor")
    def get_point_near_cursor(self, canvas_x, canvas_y, hit_radius=15):
        """
        Check if cursor is near any point handle within hit_radius pixels
        Returns the index of the nearest point, or None if no point is close enough
        """
        for i, handle in enumerate(self.point_handles):
            coords = self.canvas.coords(handle)
            if len(coords) >= 4:
                # Calculate center of the handle
                handle_center_x = (coords[0] + coords[2]) / 2
                handle_center_y = (coords[1] + coords[3]) / 2

                # Calculate distance from cursor to handle center
                distance = ((canvas_x - handle_center_x) ** 2 + (canvas_y - handle_center_y) ** 2) ** 0.5

                if distance <= hit_radius:
                    return i
        return None

    @handle_errors("annotatePanel.handle_hover_effects")
    def handle_hover_effects(self, canvas_x, canvas_y):
        """Handle hover effects for point handles"""
        point_index = self.get_point_near_cursor(canvas_x, canvas_y)

        # If we're hovering over a different point than before
        if point_index != self.hovered_point_index:
            # Reset previous hovered point
            if self.hovered_point_index is not None and self.hovered_point_index < len(self.point_handles):
                handle = self.point_handles[self.hovered_point_index]
                self.canvas.itemconfig(handle, outline="red", width=1)

            # Highlight new hovered point
            if point_index is not None:
                self.canvas.config(cursor="hand2")
                handle = self.point_handles[point_index]
                self.canvas.itemconfig(handle, outline="#78da55", width=8)
            else:
                self.canvas.config(cursor="arrow")

            self.hovered_point_index = point_index

    @handle_errors("annotatePanel.on_mouse_motion")
    def on_mouse_motion(self, event):
        """Handle mouse motion for hover effects when not dragging"""
        if self.dragging_point_index is None:  # Only show hover effects when not dragging
            self.handle_hover_effects(event.x, event.y)

    # %%remove existing point
    @handle_errors("annotatePanel.on_right_click")
    def on_right_click(self, event):
        """Remove a point if right-clicked near it, or clear all uncommitted points if clicked in empty space"""
        point_index = self.get_point_near_cursor(event.x, event.y)

        if point_index is not None:
            # Delete visual handle
            handle = self.point_handles[point_index]
            self.canvas.delete(handle)

            # Remove from current annotation data
            if self.current_annotation and point_index < len(self.current_annotation["points"]):
                del self.current_annotation["points"][point_index]

            # Remove handle from list
            del self.point_handles[point_index]

        else:
            # Right-click in empty space → clear all uncommitted points
            for handle in self.point_handles:
                self.canvas.delete(handle)
            self.point_handles.clear()

            if self.current_annotation:
                self.current_annotation["points"].clear()

        self.draw_annotation()


    # ============================================================================
    # SAVE/LOAD ANNOTATIONS
    # ============================================================================
    @handle_errors("annotatePanel.save_current_annotations")
    def save_current_annotations(self):
        image_folder = getattr(self.context, "image_folder", None)
        if not image_folder or not isinstance(image_folder, Path):
            self.context.status_bar.update("Image folder not set. Cannot save annotations.", level="warning")
            return

        annotation_folder = image_folder / "annotations"
        annotation_folder.mkdir(exist_ok=True)
        json_path = annotation_folder / "annotations.json"

        json_data = {}
        for slice_index, annotations in self.slice_annotations.items():
            slice_key = f"slice_{slice_index}"
            json_data[slice_key] = [
                {
                    "id": a.get("id"),
                    "feature": a.get("feature", "unknown"),
                    "points": a.get("points"),
                    "mode": a.get("mode"),
                    "color": a.get("color"),
                    "locked": a.get("locked", False),  # Default to False if missing
                    "timestamp": a.get("timestamp", datetime.now().isoformat())
                }
                for a in annotations
            ]

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)

        self.context.status_bar.update(f"Annotations saved to: {json_path}", level="success")

    @handle_errors("annotatePanel.load_annotations")
    def load_annotations(self, annotations_dict):
        def normalize(ann):
            return {
                "id": ann.get("id"),
                "feature": ann.get("feature", "unknown"),
                "points": ann.get("points", []),
                "mode": ann.get("mode", "line"),
                "color": ann.get("color", "#FFFFFF"),
                "locked": ann.get("locked", False),
                "timestamp": ann.get("timestamp", datetime.now().isoformat())
            }

        for slice_key, annotations in annotations_dict.items():
            slice_index = int(slice_key.replace("slice_", ""))
            self.slice_annotations[slice_index] = [normalize(a) for a in annotations]
            # Don't mark as modified on load - only when user adds new annotations

        self.draw_annotation()
    
    # ============================================================================
    # IMAGE SAVING HOOK IMPLEMENTATIONS
    # ============================================================================
    
    @handle_errors("annotatePanel.get_render_image_with_overlays")
    def get_render_image_with_overlays(self, slice_index):
        """
        Render annotations on image for saving.
        
        Args:
            slice_index: 0-based slice index
            
        Returns:
            PIL.Image: RGBA image with annotations drawn
        """
        # Check if this slice has annotations
        if slice_index not in self.slice_annotations:
            self.logger.debug(f"Slice {slice_index} not in slice_annotations")
            return None
        
        annotations = self.slice_annotations[slice_index]
        if not annotations:
            self.logger.debug(f"Slice {slice_index} has empty annotations list")
            return None
        
        self.logger.info(f"Rendering {len(annotations)} annotation(s) for slice {slice_index}")
        
        # Load the original image to get dimensions
        img_path = self.get_image_path(slice_index)
        if not img_path:
            return None
        
        original_img = Image.open(img_path)
        width, height = original_img.size
        
        # Create transparent overlay
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw each annotation
        for ann in annotations:
            pts = ann["points"]
            mode = ann["mode"]
            color = ann.get("color", "#ffffb2")
            
            # Convert hex color to RGB
            if color.startswith('#'):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                rgb_color = (r, g, b, 255)
            else:
                rgb_color = (255, 255, 178, 255)  # Default yellow
            
            if len(pts) >= 2:
                if mode == "line" or len(pts) < 4:
                    # Draw as lines - convert tuples to proper format
                    for i in range(len(pts)-1):
                        # Ensure coordinates are tuples of floats/ints
                        pt1 = tuple(pts[i]) if isinstance(pts[i], (list, tuple)) else pts[i]
                        pt2 = tuple(pts[i+1]) if isinstance(pts[i+1], (list, tuple)) else pts[i+1]
                        draw.line([pt1, pt2], fill=rgb_color, width=3)
                else:
                    # Draw as spline
                    try:
                        pts_np = np.array(pts)
                        tck, _ = splprep([pts_np[:,0], pts_np[:,1]], s=0, k=3)
                        u = np.linspace(0, 1, 500)
                        x_new, y_new = splev(u, tck)
                        spline_pts = list(zip(x_new, y_new))
                        for i in range(len(spline_pts)-1):
                            draw.line([spline_pts[i], spline_pts[i+1]], fill=rgb_color, width=3)
                    except Exception as e:
                        self.logger.warning(f"Spline rendering failed: {e}, falling back to lines")
                        # Fall back to lines if spline fails
                        for i in range(len(pts)-1):
                            pt1 = tuple(pts[i]) if isinstance(pts[i], (list, tuple)) else pts[i]
                            pt2 = tuple(pts[i+1]) if isinstance(pts[i+1], (list, tuple)) else pts[i+1]
                            draw.line([pt1, pt2], fill=rgb_color, width=3)
                
                # Note: Control points are NOT drawn in saved images
                # (only shown in interactive canvas for editing)
        
        return overlay
    
    @handle_errors("annotatePanel.get_metadata_text")
    def get_metadata_text(self):
        """
        Get metadata text from the metadata panel.
        
        Returns:
            str: Formatted metadata text
        """
        metadata_panel = self.context.get_panel("metadata")
        if not metadata_panel:
            return None
        
        try:
            operator = metadata_panel.operatorEntry.get()
            measurement = metadata_panel.measurementEntry.get()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            return f"Operator: {operator} | Measurement: {measurement} | {timestamp}"
        except:
            return None
