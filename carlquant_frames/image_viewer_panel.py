# -*- coding: utf-8 -*-
"""
Created on Mon Sep 29 15:46:17 2025

@author: meissnerto
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors

class image_viewer_panel:
    @handle_errors("error in image_viewer_panel")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_image")
        self.loadFrame = context.get_frame("carl_load")

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


    ## % Display Images
    @handle_errors("imageViewerPanel.render_zoomed_image")
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

        # Resize image
        zoomed = self.rawImage.resize((zoomed_width, zoomed_height), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(zoomed)

        # Draw image
        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, image=self.tk_image, anchor=tk.NW)
        self.canvas.update_idletasks()


    # %% render takes over the display
    @handle_errors("imageViewerPanel.display_image")
    def display_image(self, index=None):
        self.canvas.delete("all")

        specimen_id = getattr(self.context, "current_specimen_id", None)
        specimen_data = getattr(self.context, "specimen_data", {})

        if not specimen_id or specimen_id not in specimen_data:
            self.context.status_bar.update("No specimen selected.", level="warning")
            return

        image_list = specimen_data[specimen_id].images
        self.scale.configure(from_=1, to=len(image_list))

        if not image_list:
            self.context.status_bar.update("No images found for selected specimen.", level="warning")
            return

        if index is None:
            index = int(self.scale.get() - 1)

        if index < 0 or index >= len(image_list):
            return

        try:
            img_path = image_list[index]
            img = Image.open(img_path)

            self.rawImage = img.copy()
            self.zoom_level = 1.0
            self.image_offset_x = 0
            self.image_offset_y = 0

            self.render_zoomed_image()
            self.scaleValue.set(f"Slice {index + 1} / {len(image_list)}")

        except Exception as e:
            self.context.status_bar.update(f"Error displaying image {img_path}: {e}", level="error")



    # %% Annotations
    @handle_errors("imageViewerPanel.toggle_annotations")
    def toggle_annotations(self, event=None):
        self.annotations_visible = not self.annotations_visible
        self.canvas.delete("annotation")

        if self.annotations_visible:
            self.draw_annotation()
            self.draw_overlay_annotations()

        else:
            self.point_handles.clear()


    # %% Zoom
    @handle_errors("imageViewerPanel.on_mouse_wheel_zoom")
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

    # %% Paning
    @handle_errors("imageViewerPanel.start_pan")
    def start_pan(self, event):
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.canvas.config(cursor="fleur") # "hand2"

    @handle_errors("imageViewerPanel.do_pan")
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

    @handle_errors("imageViewerPanel.end_pan")
    def end_pan(self, event):
        self.is_panning = False
        self.canvas.config(cursor="arrow")


    # %% Scale Bindings
    @handle_errors("imageViewerPanel.on_arrow_left")
    def on_arrow_left(self, event):
        current = int(self.scale.get())
        if current > 1:
            self.scale.set(current - 1)
            self.display_image(current - 2)  # -2 because scale is 1-based

    @handle_errors("imageViewerPanel.on_arrow_right")
    def on_arrow_right(self, event):
        current = int(self.scale.get())
        if current < int(self.scale.cget("to")):
            self.scale.set(current + 1)
            self.display_image(current)  # current is already 1-based

    @handle_errors("imageViewerPanel.on_mouse_wheel")
    def on_mouse_wheel(self, event):
        """Handle mouse wheel scroll for Windows/macOS"""
        if event.state & 0x0004:  # Ctrl is pressed
            return  # Let canvas handle zoom
        if event.delta > 0:
            self.on_arrow_left(event)
        else:
            self.on_arrow_right(event)

    @handle_errors("imageViewerPanel.on_mouse_wheel_linux")
    def on_mouse_wheel_linux(self, event):
        """Handle mouse wheel scroll for Linux"""
        if event.state & 0x0004:  # Ctrl is pressed
            return  # Let canvas handle zoom
        if event.num == 4:
            self.on_arrow_left(event)
        elif event.num == 5:
            self.on_arrow_right(event)

    @handle_errors("imageViewerPanel.setup_scale_callback")
    def setup_scale_callback(self):
        self.scale.configure(command=self.on_scale_change)

    @handle_errors("imageViewerPanel.on_scale_change")
    def on_scale_change(self, value):
        index = int(round(float(value))) - 1
        self.display_image(index)

    # %% UI Resizing
    @handle_errors("imageViewerPanel.onResize")
    def onResize(self, event):
        self.width = event.width
        self.height = event.height

        if hasattr(self, 'tk_image'):
            self.display_image(int(self.scale.get()))
        else:
            self.instructionText()

    # %% Instructions
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
            "MISSING"

        ]

        y_offset = text_y_start
        for line in instructions:
            if line == "":
                y_offset += line_spacing // 2
                continue
            self.canvas.create_text(10, y_offset, fill="#D0D0D0", font="Sans 11",
                                    text=line, anchor=tk.NW, tags="Text")
            y_offset += line_spacing