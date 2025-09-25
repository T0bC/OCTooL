# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 11:13:52 2025

@author: meissnerto
"""

import tkinter as tk
from tkinter import ttk
from toolTip import Tooltip
from PIL import Image, ImageTk
from errorHandler import handle_errors
import numpy as np
from scipy.interpolate import splprep, splev
from pathlib import Path
import json
from datetime import datetime

class annotatePanel:
    @handle_errors("error in annotatePanel")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("image")
        self.loadFrame = context.get_frame("load")

        self.window = self.frame.winfo_toplevel()

        # Next/prevous slice
        self.window.bind("<Left>", self.on_arrow_left)
        self.window.bind("<Right>", self.on_arrow_right)
        self.window.bind("<KeyPress-h>", self.toggle_annotations)
        self.window.bind("<MouseWheel>", self.on_mouse_wheel)         # Windows/macOS
        self.window.bind("<Button-4>", self.on_mouse_wheel_linux)     # Linux scroll up
        self.window.bind("<Button-5>", self.on_mouse_wheel_linux)     # Linux scroll down

        # panning in smoothed image
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0

        # image annotation
        self.slice_annotations = {}
        self.current_annotation = None
        self.annotations_visible = True
        self.dragging_point_index = None
        self.point_handles = []
        self.overlay_handles = [] # for non drawn overlays for boolean, categorial data types and such

        # drag an existing point check
        self.dragging_started = False
        self.hovered_point_index = None # used for hiver detection

        self.frame.rowconfigure(1, weight=1)

        self.frame.rowconfigure(1, weight=1)
        self.frame.rowconfigure(3, weight=0)

        # Ensure both columns can expand
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=0)

        self.root.after(100, lambda: self.display_image(0))

        # Image Frame
        self.canvas = tk.Canvas(self.frame, width=1024, height=480, highlightthickness=0, bg='#505050')
        self.canvas.grid(row=1, column=0, columnspan=3, sticky="nsew")

        # zoom experience
        self.zoom_level = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0

        self.canvas.bind("<Configure>", self.onResize)
        self.canvas.bind("<Control-MouseWheel>", self.on_mouse_wheel_zoom)  # Windows
        self.canvas.bind("<Control-Button-4>", self.on_mouse_wheel_zoom)    # Linux scroll up
        self.canvas.bind("<Control-Button-5>", self.on_mouse_wheel_zoom)    # Linux scroll down
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        # keybind for paning the image when zoomed
        self.canvas.bind("<Control-ButtonPress-1>", self.start_pan)
        self.canvas.bind("<Control-B1-Motion>", self.do_pan)
        self.canvas.bind("<Control-ButtonRelease-1>", self.end_pan)

        # keybinds for image annotation using mouse
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)   # Detect if a point is clicked
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)      # Move selected point
        self.canvas.bind("<ButtonRelease-1>", self.on_drag_end)   # Release drag

        # hover over point
        self.canvas.bind("<Motion>", self.on_mouse_motion)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.window.bind("<KeyPress-f>", self.fit_bezier_curve)

        self.instructionText()

        self.scaleValue = tk.StringVar()
        # Insert a Scale to select current slice
        self.scale = ttk.Scale(self.frame, from_=1, to=1,
                               orient='horizontal',
                               bootstyle="warning")
        self.scale.set(1)
        self.scale.grid(row=3, column=0, columnspan=2, sticky="ew")

        self.scaleValueLabel = ttk.Label(self.frame, text="text", textvariable=self.scaleValue)
        self.scaleValueLabel.grid(row=3, column=2, sticky=tk.E)
        Tooltip(self.scale, text='Move the slider to display a different slice.', wraplength=200)

        self.setup_scale_callback()

    # %% Image anotation functions
    @handle_errors("annotatePanel.on_canvas_click")
    def on_canvas_click(self, event):
        if not hasattr(self, 'rawImage') or not hasattr(self, 'fitted_width'):
            return None  # Prevent crash
        if self.dragging_started:
            return  # Skip adding point if drag was initiated

        x, y = event.x, event.y
        img_x, img_y = self.canvas_to_image_coords(x, y)

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

        annotations = []
        if self.annotations_visible:
            annotations = self.slice_annotations.get(index, [])

        # Always include current annotation
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
                    pts_np = np.array(canvas_pts)
                    tck, _ = splprep([pts_np[:,0], pts_np[:,1]], s=0)
                    u = np.linspace(0, 1, 500)
                    x_new, y_new = splev(u, tck)
                    for i in range(len(x_new)-1):
                        self.canvas.create_line(x_new[i], y_new[i], x_new[i+1], y_new[i+1],
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
            tck, _ = splprep([pts[:, 0], pts[:, 1]], s=0)
            u = np.linspace(0, 1, 1000)
            x_new, y_new = splev(u, tck)
            length = np.sum(np.sqrt(np.diff(x_new)**2 + np.diff(y_new)**2))

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
            self.draw_annotation()
            self.draw_overlay_annotations()
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
        self.annotations_visible = True
        self.draw_annotation()

        # Schedule hiding after duration
        self.window.after(duration, self._hide_annotations_if_not_toggled)

    @handle_errors("annotatePanel._hide_annotations_if_not_toggled")
    def _hide_annotations_if_not_toggled(self):
        # Only hide if user hasn't manually re-enabled visibility
        if self.annotations_visible:
            self.annotations_visible = False
            self.draw_annotation()

    @handle_errors("annotatePanel.canvas_to_image_coords")
    def canvas_to_image_coords(self, x, y):
        if not hasattr(self, 'rawImage') or not hasattr(self, 'fitted_width'):
            return None  # Prevent crash
        current_zoom = self.zoom_level if self.zoom_level != 1.0 else self.fitted_width / self.rawImage.width
        img_x = (x - self.image_offset_x) / current_zoom
        img_y = (y - self.image_offset_y) / current_zoom
        return img_x, img_y

    @handle_errors("annotatePanel.image_to_canvas_coords")
    def image_to_canvas_coords(self, img_x, img_y):
        current_zoom = self.zoom_level if self.zoom_level != 1.0 else self.fitted_width / self.rawImage.width
        x = img_x * current_zoom + self.image_offset_x
        y = img_y * current_zoom + self.image_offset_y
        return x, y

    # %% Curve Fitting
    @handle_errors("annotatePanel.fit_bezier_curve")
    def fit_bezier_curve(self, event=None):
        if not self.current_annotation or len(self.current_annotation["points"]) < 2:
            return

        # Toggle mode for the current annotation only
        current_mode = self.current_annotation["mode"]
        self.current_annotation["mode"] = "spline" if current_mode == "line" else "line"
        self.draw_annotation()

    # %% drag existing points to new position

    @handle_errors("annotatePanel.create_new_point")
    def create_new_point(self, event):
        """Create a new annotation point"""
        x, y = event.x, event.y

        img_coords = self.canvas_to_image_coords(x, y)
        if img_coords is None:
            return

        img_x, img_y = self.canvas_to_image_coords(x, y)

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
            self.dragging_started = True

            img_x, img_y = self.canvas_to_image_coords(event.x, event.y)

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

    @handle_errors("annotatePanel.toggle_annotations")
    def toggle_annotations(self, event=None):
        self.annotations_visible = not self.annotations_visible
        self.canvas.delete("annotation")

        if self.annotations_visible:
            self.draw_annotation()
            self.draw_overlay_annotations()

        else:
            self.point_handles.clear()


    # %%
    @handle_errors("annotatePanel.setup_scale_callback")
    def setup_scale_callback(self):
        self.scale.configure(command=self.on_scale_change)

    @handle_errors("annotatePanel.on_scale_change")
    def on_scale_change(self, value):
        index = int(round(float(value))) - 1
        self.display_image(index)

    @handle_errors("error in instructionText")
    def instructionText(self):
        self.canvas.delete("all")

        self.cwidth = self.canvas.winfo_width()
        self.cheight = self.canvas.winfo_height()

        # Draw logo in top-right corner
        try:
            self.ULPhoto = "icons/WBM_UL_RGB_digital_Path.png"
            self.ULImage = Image.open(self.ULPhoto)
            self.ULImage = self.ULImage.resize((217,76), Image.Resampling.LANCZOS)
            self.ULImage = ImageTk.PhotoImage(self.ULImage)
            self.canvas.create_image(self.cwidth - 217 // 2 - 7, 45, image=self.ULImage)
        except Exception as e:
            self.context.status_bar.update(f"Failed to load logo: {e}", level="error")

        header_y = 10
        text_y_start = 5
        line_spacing = 20
        max_line_width = 80

        instructions = [
            "1. Design Annotation Columns:",
            "   - Define custom column names (e.g., Interface, Gap, etc.)",
            "   - Assign a unique key binding for each column",
            "   - Select the appropriate data type (e.g., Continuous, Categorical, Boolean)",
            "   - Choose a color to visually distinguish annotations",
            "➕ Click “Add Column” to register it in the system",
            "\n\n",
            "2. Fill Out Metadata:",
            "   - Enter operator initials (e.g., TM, CR)",
            "   - Specify measurement number (e.g., 1, 2) for repeated measurements",
            "\n\n",
            "3. Save Configuration:"
            "   - remember the location of the file"
            "\n\n",
            "4. Load Image Stack:",
            "   - Use the “Select Folder” button to load OCT images",
            "   - Load the previously saved config to restore column setup and key bindings",
            "\n\n",
            "5. Start Analyzing",
            "   - Navigate image slices using the slider, arrow keys or mouse wheel",
            "   - Annotate by pressing the assigned keys",
            "     + press [F] to use spline fitting",
            "     + press [H] to hide or show the annotations"

        ]

        y_offset = text_y_start
        for line in instructions:
            if line == "":
                y_offset += line_spacing // 2
                continue
            self.canvas.create_text(10, y_offset, fill="#D0D0D0", font="Sans 11",
                                    text=line, anchor=tk.NW, tags="Text")
            y_offset += line_spacing

    # %% Paning
    @handle_errors("annotatePanel.start_pan")
    def start_pan(self, event):
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.canvas.config(cursor="fleur") # "hand2"

    @handle_errors("annotatePanel.do_pan")
    def do_pan(self, event):
        if not self.is_panning:
            return

        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y

        self.image_offset_x += dx
        self.image_offset_y += dy

        self.pan_start_x = event.x
        self.pan_start_y = event.y

        # Clamp bounds
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        img_width = int(self.rawImage.width * self.zoom_level)
        img_height = int(self.rawImage.height * self.zoom_level)

        # Prevent dragging image completely out of view
        min_x = canvas_width - img_width
        min_y = canvas_height - img_height

        self.image_offset_x = min(max(self.image_offset_x, min_x), 0)
        self.image_offset_y = min(max(self.image_offset_y, min_y), 0)

        self.render_zoomed_image()
        self.draw_annotation()

    @handle_errors("annotatePanel.end_pan")
    def end_pan(self, event):
        self.is_panning = False
        self.canvas.config(cursor="arrow")


    # %% UI Resizing
    @handle_errors("annotatePanel.onResize")
    def onResize(self, event):
        self.width = event.width
        self.height = event.height

        if hasattr(self, 'tk_image'):
            self.display_image(int(self.scale.get()))
        else:
            self.instructionText()

    # %% Scale Binding
    @handle_errors("annotatePanel.on_arrow_left")
    def on_arrow_left(self, event):
        current = int(self.scale.get())
        if current > 1:
            self.scale.set(current - 1)
            self.display_image(current - 2)  # -2 because scale is 1-based

    @handle_errors("annotatePanel.on_arrow_right")
    def on_arrow_right(self, event):
        current = int(self.scale.get())
        if current < int(self.scale.cget("to")):
            self.scale.set(current + 1)
            self.display_image(current)  # current is already 1-based

    @handle_errors("annotatePanel.on_mouse_wheel")
    def on_mouse_wheel(self, event):
        """Handle mouse wheel scroll for Windows/macOS"""
        if event.state & 0x0004:  # Ctrl is pressed
            return  # Let canvas handle zoom
        if event.delta > 0:
            self.on_arrow_left(event)
        else:
            self.on_arrow_right(event)

    @handle_errors("annotatePanel.on_mouse_wheel_linux")
    def on_mouse_wheel_linux(self, event):
        """Handle mouse wheel scroll for Linux"""
        if event.state & 0x0004:  # Ctrl is pressed
            return  # Let canvas handle zoom
        if event.num == 4:
            self.on_arrow_left(event)
        elif event.num == 5:
            self.on_arrow_right(event)


    # %% Zooming
    @handle_errors("annotatePanel.on_mouse_wheel_zoom")
    def on_mouse_wheel_zoom(self, event):
        if not hasattr(self, 'rawImage'):
            return

        # Get mouse position relative to canvas
        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)

        # Use fitted size if zoom_level == 1.0
        if self.zoom_level == 1.0:
            current_width = getattr(self, 'fitted_width', self.rawImage.width)
            current_height = getattr(self, 'fitted_height', self.rawImage.height)
            current_zoom = current_width / self.rawImage.width
        else:
            current_zoom = self.zoom_level
        # Convert to image-relative coordinates
        rel_x = (mouse_x - self.image_offset_x) / current_zoom
        rel_y = (mouse_y - self.image_offset_y) / current_zoom

        # Update zoom level
        old_zoom = self.zoom_level
        if event.delta > 0 or getattr(event, 'num', None) == 4:
            self.zoom_level = min(self.zoom_level + 0.25, 10.0)
        elif event.delta < 0 or getattr(event, 'num', None) == 5:
            self.zoom_level = max(self.zoom_level - 0.25, 1.0)

        # Compute new offset to keep content under cursor fixed
        self.image_offset_x = mouse_x - rel_x * self.zoom_level
        self.image_offset_y = mouse_y - rel_y * self.zoom_level

        self.render_zoomed_image()
        self.draw_annotation()

    @handle_errors("annotatePanel.render_zoomed_image")
    def render_zoomed_image(self):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if self.zoom_level == 1.0:
            # Fit image to canvas while preserving aspect ratio
            img_ratio = self.rawImage.width / self.rawImage.height
            canvas_ratio = canvas_width / canvas_height

            if img_ratio > canvas_ratio:
                zoomed_width = canvas_width
                zoomed_height = int(canvas_width / img_ratio)
            else:
                zoomed_height = canvas_height
                zoomed_width = int(canvas_height * img_ratio)

            self.fitted_width = zoomed_width
            self.fitted_height = zoomed_height

            self.image_offset_x = (canvas_width - zoomed_width) // 2
            self.image_offset_y = (canvas_height - zoomed_height) // 2
        else:
            zoomed_width = int(self.rawImage.width * self.zoom_level)
            zoomed_height = int(self.rawImage.height * self.zoom_level)
            # image_offset_x/y already set via mouse wheel

        # Resize image
        zoomed = self.rawImage.resize((zoomed_width, zoomed_height), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(zoomed)

        # Draw image
        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, image=self.tk_image, anchor=tk.NW)
        self.canvas.update_idletasks()


    # %% render takes over the display
    @handle_errors("annotateImages.display_image")
    def display_image(self, index=None):
        self.canvas.delete("all")

        image_list = getattr(self.context, "image_list", [])
        self.scale.configure(from_=1, to=len(image_list))

        if not image_list:
            return

        if index is None:
            index = int(self.scale.get()-1)

        if index < 0 or index >= len(image_list):
            return

        try:
            img_path = image_list[index]['path']
            img = Image.open(img_path)

            self.rawImage = img.copy()  # Store original image

            self.zoom_level = 1.0
            self.image_offset_x = 0
            self.image_offset_y = 0

            self.rawImage = img.copy()
            self.render_zoomed_image()
            self.draw_annotation()
            self.draw_overlay_annotations()

            self.scaleValue.set(f"Slice {index + 1} / {len(image_list)}")

        except Exception as e:
            self.context.status_bar.update("Error displaying image {img_path}: {e}", level="error")


    # %% save annotations as json
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

        self.draw_annotation()
