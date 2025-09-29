# -*- coding: utf-8 -*-
"""
Created on Mon Sep 29 15:46:17 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
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