#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CarlQuant A-Scan Viewer.

Popup window showing the intensity profile (A-Scan) for a selected column in
an OCT slice. Overlays knee-point, inflection-point, shoulder-point, and
lesion-depth detection markers for visual inspection of the algorithm's decisions.

Key contents:
- AScanViewer: Modal popup with intensity plot and column selection.
- draw_intensity_profile: Renders the grayscale profile with detection overlays.
- show_knee / show_inflection / show_shoulder: Toggle individual method markers.
- synchronize_with_row: Links the viewer to the selected results-panel row.

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
from tkinter import ttk, messagebox
from PIL import Image
import numpy as np
from app.view.shared.error_handler import handle_errors
from app.logic.carlquant.carl_quant_core import (
    fit_exp2_to_profile,
    detect_depth_sigmoid_fit,
    boxcar,
    HALF_SPAN_SMOOTH_WINDOW,
)
from app.logic.carlquant.annotation_colors import (
    ROW_HIGHLIGHT_NAVIGATION_COLOR,
    ACTUAL_SURFACE_COLOR,
    INTERPOLATED_SURFACE_COLOR,
    KNEE_POINT_COLOR,
    INFLECTION_POINT_COLOR,
    SHOULDER_POINT_COLOR,
    HALF_SPAN_POINT_COLOR,
    LESION_DEPTH_PRIMARY_COLOR,
    GROUND_TRUTH_MARK_COLOR
)
from app.logic.carlquant import validation as val
from app.logic.carlquant.ground_truth import (
    GroundTruthMismatchError,
    has_ground_truth,
    load_ground_truth,
)

#: Columns stepped per Shift+arrow. Plain arrows move one column, which is the
#: point -- the slider cannot be dragged that precisely.
COLUMN_STEP_COARSE = 10


class AScanViewer:
    """Manages A-Scan viewer popup window with intensity plot and column selection."""
    
    def __init__(self, parent, style, context, specimen_id=None, slice_index=None, row_data=None):
        """
        Initialize the AScanViewer.
        
        Args:
            parent: Parent tkinter window
            style: ttkbootstrap Style object for theming
            context: Application context
            specimen_id: ID of the specimen
            slice_index: Slice index (1-based from table)
            row_data: Data from the selected row (optional)
        """
        self.parent = parent
        self.style = style
        self.context = context
        self.specimen_id = specimen_id
        self.slice_index = slice_index - 1 if slice_index else 0  # Convert to 0-based
        self.row_data = row_data
        self.dialog = None
        self.current_image = None
        self.current_column = None
        self.figure = None
        self.canvas = None
        self.slider = None
        
        # Visualization toggles
        self.show_surface = tk.BooleanVar(value=True)
        self.show_knee_point = tk.BooleanVar(value=False)
        self.show_sigmoid_inflection = tk.BooleanVar(value=False)
        self.show_sigmoid_shoulder = tk.BooleanVar(value=False)
        self.show_half_span = tk.BooleanVar(value=False)
        self.show_combined_depth = tk.BooleanVar(value=True)
        self.show_exp2_fit = tk.BooleanVar(value=False)
        self.show_sigmoid_fit = tk.BooleanVar(value=False)
        # The terms the half-span crossing is built from: smoothed profile,
        # background, peak and threshold. Drawn together because the number
        # only means something as a construction, not as four loose values.
        self.show_half_span_construction = tk.BooleanVar(value=False)
        # B-scan overlays driven from here so both views agree (good UX beats
        # hunting for the same toggle in two places).
        #
        # On by default, together with Surface Points and Combined Depth:
        # opening a result should show what was measured and where it was
        # measured from, without the operator switching four things on first.
        # The diagnostic per-method overlays stay off.
        self.show_extraction_regions = tk.BooleanVar(value=True)
        self.show_boundaries = tk.BooleanVar(value=True)
        self.zoom_to_analysis = tk.BooleanVar(value=False)  # Zoom to analysis region
        # Ground truth defaults on when marks exist for this specimen, so an
        # operator who has annotated it sees the comparison without hunting.
        self.show_ground_truth = tk.BooleanVar(value=False)

        # Operator marks for the displayed slice, {slice_index: [(x, y), ...]}
        self.ground_truth_marks = {}
        self._ground_truth_default_applied_for = None  # Specimen the default was set for

        # Cached specimen data
        self.specimen = None
        self.slice_result = None
        
        # Hover annotation data
        self.annotation_points = []  # List of (x, y, label, artist) tuples
        self.hover_annotation = None  # Matplotlib annotation object
        
        # Image viewer synchronization callback
        self.image_viewer_redraw_callback = None  # Callback to trigger image viewer redraw
        
        # Slider interaction state
        self.slider_dragging = False  # True when user is actively dragging the slider
    
    @handle_errors("AScanViewer.show")
    def show(self):
        """Show the A-Scan viewer dialog (non-blocking)."""
        # Navigate to the correct image first
        self._navigate_to_image()
        
        # Load the image
        if not self._load_image():
            return
        
        # Create non-modal dialog (no grab_set() for non-blocking behavior)
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"A-Scan Viewer - {self.specimen_id} - Slice {self.slice_index + 1}")
        self.dialog.transient(self.parent)
        # NOTE: No grab_set() to keep it non-blocking
        
        # Set size and position (narrower but taller, responsive to screen height)
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        dialog_width = 570  # Fits the four toggle groups without dead space
        dialog_height = int(screen_height * 0.75)  # 75% of screen height
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Apply dark theme colors
        bg_color = self.style.colors.bg
        self.dialog.configure(bg=bg_color)
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=8)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Get image dimensions for slider range
        img_width = self.current_image.shape[1]
        
        # Load specimen data for annotations
        self._load_specimen_data()
        
        # Toggles, grouped by what they answer: which depth was reported,
        # how a method arrived at it, what to overlay on the B-scan, and how
        # to frame the plot. Scattered checkboxes made related ones hard to
        # find; four labelled columns keep each question in one place.
        toggles_frame = ttk.LabelFrame(main_frame, text="Display Options", padding=6)
        toggles_frame.pack(fill=tk.X, pady=(0, 6))

        groups = [
            ("Detected Depths", [
                ("Combined Depth", self.show_combined_depth, None),
                ("Half-Span", self.show_half_span, None),
                ("Knee Point", self.show_knee_point, None),
                ("Sigmoid Inflection", self.show_sigmoid_inflection, None),
                ("Sigmoid Shoulder", self.show_sigmoid_shoulder, None),
            ]),
            ("Method Internals", [
                ("Exp2 Fit Curve", self.show_exp2_fit, None),
                ("Sigmoid Fit Curve", self.show_sigmoid_fit, None),
                ("Half-Span Construction", self.show_half_span_construction, None),
            ]),
            ("Image Overlays", [
                ("Surface Points", self.show_surface, None),
                ("Extraction Regions", self.show_extraction_regions, None),
                ("Boundaries", self.show_boundaries, None),
                ("Ground Truth", self.show_ground_truth,
                 self._on_ground_truth_toggled),
            ]),
            ("View", [
                ("Zoom to Analysis", self.zoom_to_analysis,
                 self._on_zoom_to_analysis_toggled),
            ]),
        ]

        for column, (heading, entries) in enumerate(groups):
            toggles_frame.columnconfigure(column, weight=1)
            ttk.Label(toggles_frame, text=heading,
                      font=('Segoe UI', 8, 'bold')).grid(
                row=0, column=column, sticky='w', padx=4, pady=(0, 2))
            for row, (text, variable, command) in enumerate(entries, start=1):
                ttk.Checkbutton(
                    toggles_frame, text=text, variable=variable,
                    command=command or (
                        lambda: self._update_plot(force_image_sync=True))
                ).grid(row=row, column=column, sticky='w', padx=4, pady=1)

        # Slider frame with label above
        slider_container = ttk.Frame(main_frame)
        slider_container.pack(fill=tk.X, pady=(0, 6))
        
        # Label above slider
        slider_label = ttk.Label(
            slider_container,
            text="A-Scan",
            font=('Segoe UI', 10, 'bold')
        )
        slider_label.pack(side=tk.TOP, anchor='w', pady=(0, 2))
        
        # Slider and column number in horizontal layout
        slider_frame = ttk.Frame(slider_container)
        slider_frame.pack(fill=tk.X)
        
        # Initialize to middle column
        self.current_column = img_width // 2
        
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=img_width - 1,
            orient=tk.HORIZONTAL,
            command=self._on_slider_change
        )
        
        # Bind mouse events to track slider dragging state
        self.slider.bind('<ButtonPress-1>', self._on_slider_press)
        self.slider.bind('<ButtonRelease-1>', self._on_slider_release)
        self.slider.set(self.current_column)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Plot frame
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True)
        
        # Force window to update geometry before creating plot
        # This ensures the plot knows the correct size on initialization
        self.dialog.update_idletasks()
        
        # Create matplotlib figure
        self._create_plot(plot_frame)
        
        # Bind Escape key to close
        self.dialog.bind('<Escape>', lambda e: self.on_close())

        # Arrow keys step the A-scan column; dragging the slider to a specific
        # column is hard at this width. Bound on the dialog, not globally, so
        # the image viewer canvas keeps its own Left/Right for slice
        # navigation -- Tk routes keys to the focused window.
        self.dialog.bind('<Left>', lambda e: self._step_column(-1))
        self.dialog.bind('<Right>', lambda e: self._step_column(1))
        self.dialog.bind('<Shift-Left>', lambda e: self._step_column(-COLUMN_STEP_COARSE))
        self.dialog.bind('<Shift-Right>', lambda e: self._step_column(COLUMN_STEP_COARSE))
        
        # Bind window close event to clear indicator
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Register callback with image viewer for slice synchronization
        image_panel = self.context.get_panel("carl_image")
        if image_panel:
            image_panel.register_ascan_viewer_callback(self.on_slice_changed)
            # Store reference for triggering redraws when checkboxes change
            self.image_viewer_redraw_callback = image_panel.render_zoomed_image
        
        # Draw initial A-scan indicator in image viewer
        self._update_image_indicator()
    
    @handle_errors("AScanViewer._navigate_to_image")
    def _navigate_to_image(self):
        """Navigate the image viewer to the correct specimen and slice."""
        # Get the image viewer panel
        image_panel = self.context.get_panel("carl_image")
        if not image_panel:
            return
        
        # Set the current specimen if different
        if self.context.current_specimen_id != self.specimen_id:
            self.context.current_specimen_id = self.specimen_id
        
        # Navigate to the correct slice
        image_panel.display_image(self.slice_index)
        
        # Ensure overlays are visible
        if not image_panel.overlays_visible:
            image_panel.toggle_overlays()
    
    @handle_errors("AScanViewer._load_image")
    def _load_image(self):
        """Load the image for the current specimen and slice."""
        specimen_data = getattr(self.context, "specimen_data", {})
        
        if self.specimen_id not in specimen_data:
            if hasattr(self.context, 'status_bar'):
                self.context.status_bar.update(f"Specimen '{self.specimen_id}' not found.", level="error")
            return False
        
        specimen = specimen_data[self.specimen_id]
        
        if self.slice_index < 0 or self.slice_index >= len(specimen.images):
            if hasattr(self.context, 'status_bar'):
                self.context.status_bar.update(f"Invalid slice index: {self.slice_index}", level="error")
            return False
        
        try:
            img_path = specimen.images[self.slice_index]
            img = Image.open(img_path)
            
            # Convert to grayscale if not already
            if img.mode != 'L':
                img = img.convert('L')
            
            # Convert to numpy array
            self.current_image = np.array(img)
            return True
            
        except Exception as e:
            if hasattr(self.context, 'status_bar'):
                self.context.status_bar.update(f"Error loading image: {e}", level="error")
            return False
    
    @handle_errors("AScanViewer._load_specimen_data")
    def _load_specimen_data(self):
        """Load specimen and slice result data for annotations."""
        specimen_data = getattr(self.context, "specimen_data", {})
        
        if self.specimen_id not in specimen_data:
            return
        
        self.specimen = specimen_data[self.specimen_id]
        
        # Get slice result if available
        if hasattr(self.specimen, 'results') and self.slice_index in self.specimen.results:
            self.slice_result = self.specimen.results[self.slice_index]
        else:
            self.slice_result = None

        self._load_ground_truth_marks()

    def _load_ground_truth_marks(self):
        """Load operator marks for this specimen, if any have been recorded.

        The toggle defaults on when ground truth exists so an annotated
        specimen shows the comparison immediately, and stays inert otherwise.
        """
        if self.specimen is None:
            return

        try:
            self.ground_truth_marks = load_ground_truth(self.specimen)
        except GroundTruthMismatchError:
            # Marks from another specimen would be meaningless here; the image
            # viewer reports the mismatch, so stay silent and show nothing.
            self.ground_truth_marks = {}

        # Apply the "on when ground truth exists" default once per specimen, so
        # a slice change does not undo the operator turning the toggle off.
        if self._ground_truth_default_applied_for != self.specimen_id:
            self._ground_truth_default_applied_for = self.specimen_id
            self.show_ground_truth.set(
                bool(self.ground_truth_marks) and has_ground_truth(self.specimen))

    def _marks_for_current_slice(self):
        """Operator marks on the slice being viewed."""
        return self.ground_truth_marks.get(self.slice_index, [])

    def _nearest_mark(self, tolerance=val.DEFAULT_TOLERANCE):
        """The operator mark nearest the displayed column, or None.

        Marks are placed per A-scan column but rarely land exactly on the one
        being viewed, so a small tolerance is allowed; beyond it there is no
        ground truth for this column and nothing is drawn.
        """
        marks = self._marks_for_current_slice()
        if not marks or self.current_column is None:
            return None

        nearest = min(marks, key=lambda mark: abs(mark[0] - self.current_column))
        if abs(nearest[0] - self.current_column) > tolerance:
            return None
        return nearest

    def _plot_ground_truth(self, column_data, surface_y, metadata,
                           lesion_detection_data):
        """Draw the operator's mark for this column and each method's error.

        The mark is a horizontal line across the A-scan at its depth, so it can
        be read against the intensity profile that produced the detection.
        """
        mark = self._nearest_mark()
        if mark is not None:
            mark_y = mark[1]
            is_interpolated = False
        else:
            # Marks sit ~22 px apart, so most columns fall between two of them.
            # Interpolating keeps a reference on screen; it is labelled as
            # inferred and never reaches the scoring in the results panel.
            mark_y = val.interpolated_mark_at(self._marks_for_current_slice(),
                                              self.current_column)
            if mark_y is None:
                return
            is_interpolated = True

        self.ax.axhline(y=mark_y, color=GROUND_TRUTH_MARK_COLOR, linewidth=1.5,
                        linestyle=':' if is_interpolated else '--', zorder=3,
                        label='Ground Truth (interp.)' if is_interpolated else 'Ground Truth')

        intensity = (column_data[int(mark_y)]
                     if 0 <= int(mark_y) < len(column_data) else 128)

        lines = ['Ground Truth (interpolated)' if is_interpolated
                 else 'Ground Truth (operator)',
                 f'X: {intensity:.1f}',
                 f'Y: {mark_y:.1f}']
        if surface_y is not None:
            lines.append(f'Depth: {mark_y - surface_y:.1f}px')

        # Signed error of every enabled method: + too deep, - too shallow.
        errors = self._method_errors_against(mark_y, surface_y, metadata,
                                             lesion_detection_data)
        if errors:
            lines.append('')
            lines.append('Error (+ deep / - shallow):')
            lines.extend(errors)

        if is_interpolated:
            lines.append('')
            lines.append('Interpolated between marks - not scored')

        self._plot_point_with_hover(
            intensity, mark_y, '\n'.join(lines),
            'Ground Truth (interp.)' if is_interpolated else 'Ground Truth',
            '+' if is_interpolated else 'x',
            GROUND_TRUTH_MARK_COLOR, 12, 7)

    def _method_errors_against(self, mark_y, surface_y, metadata,
                               lesion_detection_data):
        """Signed error of each enabled method against one mark, as text lines."""
        if surface_y is None:
            return []

        enabled = [
            ('Combined', self.show_combined_depth,
             (lesion_detection_data or {}).get('lesion_depth_px')),
            ('Half-Span', self.show_half_span, metadata.get('half_span_depth')),
            ('Knee', self.show_knee_point, metadata.get('knee_depth')),
            ('Inflection', self.show_sigmoid_inflection,
             metadata.get('inflection_depth')),
            ('Shoulder', self.show_sigmoid_shoulder, metadata.get('shoulder_depth')),
        ]

        lines = []
        for label, toggle, depth in enabled:
            if not toggle.get() or depth is None or np.isnan(depth):
                continue
            lines.append(f'  {label}: {surface_y + depth - mark_y:+.1f}px')
        return lines
    
    @handle_errors("AScanViewer._create_plot")
    def _create_plot(self, parent_frame):
        """Create the matplotlib plot for A-Scan visualization."""
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        # Create figure with dark background (smaller width for narrow window)
        # Wider than tall, matching a dialog that fits four toggle groups.
        self.figure = Figure(figsize=(6, 6), facecolor='#2b2b2b')
        self.ax = self.figure.add_subplot(111)
        
        # Set dark theme for plot
        self.ax.set_facecolor('#1e1e1e')
        self.ax.spines['bottom'].set_color('#dcdcdc')
        self.ax.spines['top'].set_color('#dcdcdc')
        self.ax.spines['left'].set_color('#dcdcdc')
        self.ax.spines['right'].set_color('#dcdcdc')
        self.ax.tick_params(colors='#dcdcdc', which='both', labelsize=8)
        self.ax.xaxis.label.set_color('#dcdcdc')
        self.ax.yaxis.label.set_color('#dcdcdc')
        self.ax.title.set_color('#dcdcdc')
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.figure, parent_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Create hover annotation (initially invisible)
        self.hover_annotation = self.ax.annotate(
            '', xy=(0, 0), xytext=(10, 10),
            textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.5', fc='#3a3a3a', ec='#dcdcdc', alpha=0.95),
            color='#dcdcdc',
            fontsize=8,
            visible=False,
            zorder=100
        )
        
        # Connect mouse motion event for hover functionality
        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
        
        # Initial plot - force draw to ensure proper rendering
        self._update_plot()
        self.canvas.draw_idle()
        self.figure.tight_layout(pad=1.2)
        self.canvas.draw()
    
    def _plot_point_with_hover(self, x, y, hover_label, legend_label, marker='o', color='white', markersize=8, zorder=5):
        """Plot a point and store it for hover functionality.
        
        Args:
            x: X coordinate (intensity)
            y: Y coordinate (depth)
            hover_label: Label for hover tooltip (with coordinates)
            legend_label: Label for legend (without coordinates)
            marker: Matplotlib marker style
            color: Marker color
            markersize: Size of marker
            zorder: Z-order for layering
        
        Returns:
            The artist object from the plot
        """
        artist = self.ax.plot(x, y, marker, color=color, markersize=markersize, 
                             label=legend_label, zorder=zorder, picker=5)[0]
        self.annotation_points.append((x, y, hover_label, artist))
        return artist
    
    @handle_errors("AScanViewer._update_plot")
    def _update_plot(self, force_image_sync=False):
        """Update the plot with current column data and annotations.
        
        Args:
            force_image_sync: If True, always trigger image viewer redraw.
                            If False, skip redraw during slider dragging for performance.
        
        The image viewer redraw synchronizes component method visibility (knee/inflection/shoulder)
        with the checkbox states. This is needed when checkboxes change, but not during
        slider movements where only the column position changes.
        """
        if self.current_image is None or self.current_column is None:
            return
        
        # Trigger image viewer redraw only if:
        # 1. Explicitly requested (checkbox change), OR
        # 2. Not currently dragging the slider
        # This prevents expensive full canvas redraws during slider movement
        if force_image_sync or not self.slider_dragging:
            if self.image_viewer_redraw_callback is not None:
                try:
                    self.image_viewer_redraw_callback()
                except Exception:
                    pass  # Silently ignore if image viewer is not available
        
        # Extract column (A-scan)
        column_data = self.current_image[:, self.current_column]
        
        # Y-axis is depth (0 at top, increasing downward)
        y_positions = np.arange(len(column_data))
        
        # Clear previous plot and annotation points
        self.ax.clear()
        self.annotation_points = []  # Reset annotation points for new plot
        
        # Recreate hover annotation after clearing (ax.clear() removes all artists)
        if self.hover_annotation is not None:
            self.hover_annotation = self.ax.annotate(
                '', xy=(0, 0), xytext=(10, 10),
                textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='#3a3a3a', ec='#dcdcdc', alpha=0.95),
                color='#dcdcdc',
                fontsize=8,
                visible=False,
                zorder=100
            )
        
        # Get surface and lesion depth data for this column FIRST
        surface_y = None
        interpolated_surface_y = None
        lesion_detection_data = None
        
        if self.slice_result:
            # Get surface points
            if hasattr(self.slice_result, 'surface') and self.slice_result.surface:
                surface = self.slice_result.surface
                
                # Find actual surface point for this column
                if 'actual_surface' in surface.fitted_curves:
                    for x, y in surface.fitted_curves['actual_surface']:
                        if x == self.current_column:
                            surface_y = y
                            break
                
                # Find interpolated surface point for this column
                if 'interpolated_surface' in surface.fitted_curves:
                    for x, y in surface.fitted_curves['interpolated_surface']:
                        if x == self.current_column:
                            interpolated_surface_y = y
                            break
            
            # Get lesion depth detection data for this column
            if hasattr(self.slice_result, 'lesion_depth') and self.slice_result.lesion_depth:
                lesion_depth = self.slice_result.lesion_depth
                if lesion_depth.lesion_detection_data and self.current_column in lesion_depth.lesion_detection_data:
                    lesion_detection_data = lesion_depth.lesion_detection_data[self.current_column]
        
        # Plot intensity vs depth (main A-scan line)
        # Split into parts: before surface (cyan) and after surface (orange for fitting region)
        if surface_y is not None:
            # Part before surface
            before_surface = y_positions <= surface_y
            if np.any(before_surface):
                self.ax.plot(column_data[before_surface], y_positions[before_surface], 
                            color='#00d4ff', linewidth=1.0, label='A-Scan (above surface)', zorder=1)
            
            # Part after surface (fitting region, typically 200px)
            fitting_region = (y_positions > surface_y) & (y_positions <= surface_y + 200)
            remaining_region = y_positions > surface_y + 200
            
            # Fitting region in dark green (better contrast for sigmoid fit)
            if np.any(fitting_region):
                self.ax.plot(column_data[fitting_region], y_positions[fitting_region], 
                            color='#1c6b46', linewidth=1.0, label='A-Scan (fitting region)', zorder=1)
            
            # Remaining region in darker cyan
            if np.any(remaining_region):
                self.ax.plot(column_data[remaining_region], y_positions[remaining_region], 
                            color='#0088aa', linewidth=1.0, label='A-Scan (below fitting)', zorder=1)
        else:
            # No surface detected, plot entire A-scan in cyan
            self.ax.plot(column_data, y_positions, color='#00d4ff', linewidth=1.0, label='A-Scan', zorder=1)
        
        # Plot surface points
        if self.show_surface.get():
            if surface_y is not None:
                intensity = column_data[int(surface_y)] if int(surface_y) < len(column_data) else 128
                self._plot_point_with_hover(
                    intensity, surface_y, 
                    f'Actual Surface\nX: {intensity:.1f}\nY: {surface_y:.1f}',
                    'Actual Surface',
                    'o', ACTUAL_SURFACE_COLOR, 8, 5)
            
            if interpolated_surface_y is not None:
                intensity = column_data[int(interpolated_surface_y)] if int(interpolated_surface_y) < len(column_data) else 128
                self._plot_point_with_hover(
                    intensity, interpolated_surface_y,
                    f'Interpolated Surface\nX: {intensity:.1f}\nY: {interpolated_surface_y:.1f}',
                    'Interpolated Surface',
                    's', INTERPOLATED_SURFACE_COLOR, 8, 5)
        
        # Plot detection method results if available
        if lesion_detection_data and surface_y is not None:
            metadata = lesion_detection_data.get('detection_metadata', {})
            
            # Knee point (relative to surface)
            if self.show_knee_point.get() and 'knee_depth' in metadata:
                knee_depth = metadata['knee_depth']
                if not np.isnan(knee_depth):
                    absolute_depth = surface_y + knee_depth
                    if int(absolute_depth) < len(column_data):
                        intensity = column_data[int(absolute_depth)]
                        self._plot_point_with_hover(
                            intensity, absolute_depth,
                            f'Knee Point\nX: {intensity:.1f}\nY: {absolute_depth:.1f}\nDepth: {knee_depth:.1f}px',
                            'Knee Point',
                            '^', KNEE_POINT_COLOR, 10, 4)
            
            # Sigmoid inflection point (relative to surface)
            if self.show_sigmoid_inflection.get() and 'inflection_depth' in metadata:
                inflection_depth = metadata['inflection_depth']
                if not np.isnan(inflection_depth):
                    absolute_depth = surface_y + inflection_depth
                    if int(absolute_depth) < len(column_data):
                        intensity = column_data[int(absolute_depth)]
                        self._plot_point_with_hover(
                            intensity, absolute_depth,
                            f'Sigmoid Inflection\nX: {intensity:.1f}\nY: {absolute_depth:.1f}\nDepth: {inflection_depth:.1f}px',
                            'Sigmoid Inflection',
                            'v', INFLECTION_POINT_COLOR, 10, 4)
            
            # Sigmoid shoulder point (relative to surface)
            if self.show_sigmoid_shoulder.get() and 'shoulder_depth' in metadata:
                shoulder_depth = metadata['shoulder_depth']
                if not np.isnan(shoulder_depth):
                    absolute_depth = surface_y + shoulder_depth
                    if int(absolute_depth) < len(column_data):
                        intensity = column_data[int(absolute_depth)]
                        self._plot_point_with_hover(
                            intensity, absolute_depth,
                            f'Sigmoid Shoulder\nX: {intensity:.1f}\nY: {absolute_depth:.1f}\nDepth: {shoulder_depth:.1f}px',
                            'Sigmoid Shoulder',
                            'd', SHOULDER_POINT_COLOR, 10, 4)

            # Half-span crossing (relative to surface)
            if self.show_half_span.get() and 'half_span_depth' in metadata:
                half_span_depth = metadata['half_span_depth']
                if half_span_depth is not None and not np.isnan(half_span_depth):
                    absolute_depth = surface_y + half_span_depth
                    if int(absolute_depth) < len(column_data):
                        intensity = column_data[int(absolute_depth)]
                        fraction = metadata.get('half_span_fraction', float('nan'))
                        self._plot_point_with_hover(
                            intensity, absolute_depth,
                            f'Half-Span Crossing\nX: {intensity:.1f}\nY: {absolute_depth:.1f}\n'
                            f'Depth: {half_span_depth:.1f}px\nFraction: {fraction:.2f}',
                            'Half-Span Crossing',
                            'o', HALF_SPAN_POINT_COLOR, 10, 4)
            
            # Combined depth (final result, relative to surface)
            if self.show_combined_depth.get():
                # Raw pixel depth, never the refractive-index-corrected one:
                # this marker has to sit on the boundary visible in the image,
                # and the corrected value does not correspond to a pixel row.
                combined_depth = lesion_detection_data.get('lesion_depth_px')
                if combined_depth is None:
                    # Configs written before the field was split.
                    combined_depth = lesion_detection_data.get('knee_depth')
                
                if combined_depth is not None and not np.isnan(combined_depth):
                    absolute_depth = surface_y + combined_depth
                    if int(absolute_depth) < len(column_data):
                        intensity = column_data[int(absolute_depth)]
                        self._plot_point_with_hover(
                            intensity, absolute_depth,
                            f'Combined Depth\nX: {intensity:.1f}\nY: {absolute_depth:.1f}\nDepth: {combined_depth:.1f}px',
                            'Combined Depth',
                            '*', LESION_DEPTH_PRIMARY_COLOR, 15, 6)

            # Operator ground truth for this column, with each enabled method's
            # signed error against it. Seeing the mark against the intensity
            # profile is what makes a disagreement diagnosable rather than
            # merely visible.
            if self.show_ground_truth.get():
                self._plot_ground_truth(column_data, surface_y, metadata,
                                        lesion_detection_data)

            # Plot fit curves (computed on-demand from image data)
            # Get the profile start position
            profile_start_y = lesion_detection_data.get('profile_start_y', surface_y)
            
            # Extract intensity profile from image (search_depth=200 as in algorithm)
            search_depth = 200
            if surface_y is not None and int(surface_y) < len(column_data):
                start_y = int(surface_y)
                end_y = min(start_y + search_depth, len(column_data))
                intensity_profile = column_data[start_y:end_y]
                depth_indices = np.arange(len(intensity_profile))
                
                # Exp2 fit curve (compute on-demand)
                if self.show_exp2_fit.get() and len(intensity_profile) > 10:
                    try:
                        fit_result = fit_exp2_to_profile(intensity_profile, depth_indices)
                        if fit_result is not None:
                            exp2_fit, _ = fit_result
                            # Create y positions starting from profile start
                            y_fit = np.arange(len(exp2_fit)) + profile_start_y
                            # Only plot points within image bounds
                            valid_indices = y_fit < len(column_data)
                            if np.any(valid_indices):
                                self.ax.plot(exp2_fit[valid_indices], y_fit[valid_indices], '--', 
                                           color='#48dbfb', linewidth=2.5, 
                                           label='Exp2 Fit', alpha=0.9, zorder=3)
                    except Exception:
                        pass  # Silently skip if fitting fails
                
                # Sigmoid fit curve (compute on-demand)
                if self.show_sigmoid_fit.get() and len(intensity_profile) > 10:
                    try:
                        _, _, sigmoid_meta = detect_depth_sigmoid_fit(intensity_profile, depth_indices)
                        if sigmoid_meta.get('success') and 'fitted_curve' in sigmoid_meta:
                            sigmoid_fit = np.array(sigmoid_meta['fitted_curve'])
                            # Create y positions starting from profile start
                            y_fit = np.arange(len(sigmoid_fit)) + profile_start_y
                            # Only plot points within image bounds
                            valid_indices = y_fit < len(column_data)
                            if np.any(valid_indices):
                                self.ax.plot(sigmoid_fit[valid_indices], y_fit[valid_indices], '--', 
                                           color='#feca57', linewidth=2.5, 
                                           label='Sigmoid Fit', alpha=0.9, zorder=3)
                    except Exception:
                        pass  # Silently skip if fitting fails

                # Half-span construction: every term the crossing is built
                # from, so the reported depth can be read off the plot rather
                # than taken on trust.
                if self.show_half_span_construction.get():
                    self._plot_half_span_construction(
                        metadata, intensity_profile, profile_start_y,
                        len(column_data))

        # Set labels and title (smaller fonts for narrow window)
        self.ax.set_xlabel('Gray Value', fontsize=9, color='#dcdcdc')
        self.ax.set_ylabel('Depth (px)', fontsize=9, color='#dcdcdc')
        self.ax.set_title(f'A-Scan at Column {self.current_column}', fontsize=10, color='#dcdcdc', pad=8)
        
        # Set limits
        self.ax.set_xlim(0, 255)
        
        # Y-axis limits: zoom to analysis region if enabled
        if self.zoom_to_analysis.get() and surface_y is not None:
            # Show from surface to ~250px below (analysis region + some margin)
            y_min = max(0, int(surface_y) - 20)  # Small margin above surface
            y_max = min(len(column_data), int(surface_y) + 250)  # Analysis region + margin
            self.ax.set_ylim(y_max, y_min)  # Invert Y-axis (0 at top)
        else:
            # Show full A-scan
            self.ax.set_ylim(len(column_data), 0)  # Invert Y-axis (0 at top)
        
        # Grid
        self.ax.grid(True, alpha=0.2, color='#dcdcdc')
        
        # Legend (only if there are annotations to show)
        handles, labels = self.ax.get_legend_handles_labels()
        if len(handles) > 1:  # More than just the A-Scan line
            self.ax.legend(loc='lower right', fontsize=7, framealpha=0.9, 
                          facecolor='#2b2b2b', edgecolor='#dcdcdc', labelcolor='#dcdcdc')
        
        # Tight layout
        self.figure.tight_layout(pad=1.2)
        
        # Redraw
        self.canvas.draw()
    
    @handle_errors("AScanViewer._on_slider_press")
    def _on_slider_press(self, event):
        """Handle slider mouse press - start dragging state."""
        self.slider_dragging = True
    
    @handle_errors("AScanViewer._on_slider_release")
    def _on_slider_release(self, event):
        """Handle slider mouse release - end dragging state and sync with image viewer."""
        self.slider_dragging = False
        # Trigger final sync with image viewer after drag completes
        if self.image_viewer_redraw_callback is not None:
            try:
                self.image_viewer_redraw_callback()
            except Exception:
                pass  # Silently ignore if image viewer is not available
    
    @handle_errors("AScanViewer._on_slider_change")
    def _on_slider_change(self, value):
        """Handle slider value change.
        
        During slider dragging, only updates the A-scan indicator line without
        triggering expensive full canvas redraws. The full sync happens when
        the slider is released.
        """
        self.current_column = int(float(value))
        if hasattr(self, 'ax'):
            self._update_plot()  # Will skip image sync during dragging
        # Update indicator line in image viewer (lightweight operation)
        self._update_image_indicator()
    
    @handle_errors("AScanViewer._plot_half_span_construction")
    def _plot_half_span_construction(self, metadata, intensity_profile,
                                     profile_start_y, image_height):
        """Draw how the half-span crossing reached its depth.

        Four things, which together are the whole method: the boxcar-smoothed
        profile the test actually runs on, the background median and surface
        peak that set the contrast span, and the threshold between them that
        the profile has to cross and stay below.

        The smoothed profile is recomputed here rather than stored -- it is a
        boxcar of the intensity profile, which is already saved.
        """
        background = metadata.get('half_span_background')
        peak = metadata.get('half_span_peak')
        threshold = metadata.get('half_span_threshold')
        window = metadata.get('half_span_smooth_window', HALF_SPAN_SMOOTH_WINDOW)

        if len(intensity_profile) > 1 and window:
            smoothed = boxcar(np.asarray(intensity_profile, dtype=float),
                               int(window))
            y_smooth = np.arange(len(smoothed)) + profile_start_y
            visible = y_smooth < image_height
            if np.any(visible):
                self.ax.plot(smoothed[visible], y_smooth[visible], '-',
                             color='#a29bfe', linewidth=1.8,
                             label=f'Smoothed (w={int(window)})',
                             alpha=0.9, zorder=2)

        # Vertical lines: the plot is gray value on x, depth on y.
        fraction = metadata.get('half_span_fraction')
        for value, color, style, label in (
                (background, '#7f8c8d', ':', 'Background'),
                (peak, '#ffffff', ':', 'Peak'),
                (threshold, HALF_SPAN_POINT_COLOR, '--',
                 'Threshold' if fraction is None or not np.isfinite(fraction)
                 else f'Threshold ({fraction:.2f})')):
            if value is None or not np.isfinite(value):
                continue
            self.ax.axvline(x=value, color=color, linestyle=style,
                            linewidth=1.4, alpha=0.85, label=label, zorder=2)

        # A crossing that never held for the full window is the weaker case,
        # so say when that happened rather than showing an unqualified line.
        if metadata.get('half_span_sustained') is False:
            self.ax.text(0.02, 0.02, 'crossing not sustained',
                         transform=self.ax.transAxes, fontsize=7,
                         color=HALF_SPAN_POINT_COLOR, alpha=0.9)

    @handle_errors("AScanViewer._step_column")
    def _step_column(self, delta):
        """Move the selected A-scan by ``delta`` columns, clamped to the image.

        Returning "break" stops Tk passing the arrow key on to the slider,
        which would otherwise move it a second time.
        """
        if self.slider is None or self.current_column is None:
            return "break"
        upper = int(float(self.slider.cget("to")))
        target = max(0, min(upper, self.current_column + delta))
        if target != self.current_column:
            self.slider.set(target)  # Fires _on_slider_change, which redraws.
        return "break"

    @handle_errors("AScanViewer._on_ground_truth_toggled")
    def _on_ground_truth_toggled(self):
        """Draw the operator marks, or explain how to create them.

        Switching the toggle on with nothing to show would otherwise look
        broken. The box explains what ground truth is and how to add it, then
        clears the toggle so the checkbox matches what is actually drawn --
        leaving it checked would strand the user with an empty overlay and no
        prompt to act on.
        """
        if self.show_ground_truth.get() and not self._marks_for_current_slice():
            self.show_ground_truth.set(False)
            messagebox.showinfo(
                "No Ground Truth Yet",
                "No operator marks exist for this specimen.\n\n"
                "Ground truth is where you judge the lesion to end, marked by "
                "eye on the OCT image. It is what the detected depths are "
                "scored against.\n\n"
                "To create it:\n"
                "1. Enable Validation Mode in the image viewer\n"
                "2. Click along the lesion boundary to place marks\n"
                "3. Re-open this toggle to compare",
                parent=self.dialog,
            )
            return
        self._update_plot(force_image_sync=True)

    @handle_errors("AScanViewer._on_zoom_to_analysis_toggled")
    def _on_zoom_to_analysis_toggled(self):
        """Zoom both views to the analysis region, or restore both.

        The A-scan zooms in depth and the B-scan in lateral extent -- two
        views of the same region, so one toggle drives both.
        """
        self._sync_image_analysis_zoom()
        self._update_plot(force_image_sync=True)

    def _sync_image_analysis_zoom(self):
        """Push the current zoom-to-analysis state to the image viewer."""
        image_panel = self.context.get_panel("carl_image")
        if image_panel and hasattr(image_panel, "sync_analysis_zoom"):
            image_panel.sync_analysis_zoom(self.zoom_to_analysis.get())

    @handle_errors("AScanViewer._update_image_indicator")
    def _update_image_indicator(self):
        """Update the A-scan indicator line in the image viewer."""
        image_panel = self.context.get_panel("carl_image")
        if image_panel and self.current_column is not None:
            image_panel.draw_ascan_indicator(self.current_column)
    
    def on_close(self):
        """Handle window close event - clear indicator and destroy window."""
        # Unregister callback from image viewer
        image_panel = self.context.get_panel("carl_image")
        if image_panel:
            image_panel.unregister_ascan_viewer_callback()
            # Forget, not just clear: the redraw below would otherwise restore
            # the indicator for a viewer that is closing.
            image_panel.forget_ascan_indicator()
            # Release the analysis zoom with the viewer that asked for it.
            if hasattr(image_panel, "sync_analysis_zoom"):
                image_panel.sync_analysis_zoom(False)
            # Trigger redraw to hide component methods
            try:
                image_panel.render_zoomed_image()
            except Exception:
                pass  # Silently ignore if redraw fails
        
        # Clear active viewer reference in results panel and switch back to green highlighting
        results_panel = self.context.get_panel("carl_results")
        if results_panel and hasattr(results_panel, 'active_ascan_viewer'):
            results_panel.active_ascan_viewer = None
            # Switch back to green highlighting when A-Scan viewer closes
            if hasattr(results_panel, 'set_highlight_color'):
                results_panel.set_highlight_color(ROW_HIGHLIGHT_NAVIGATION_COLOR)
        
        # Destroy the dialog
        self.dialog.destroy()
    
    @handle_errors("AScanViewer.update_to_slice")
    def update_to_slice(self, specimen_id, slice_index):
        """Update the viewer to display a different specimen/slice.
        
        This method allows reusing an existing A-Scan viewer window instead of
        creating new instances when the user navigates to different slices.
        
        Args:
            specimen_id: ID of the specimen
            slice_index: Slice index (1-based from table)
        """
        # Update specimen and slice
        self.specimen_id = specimen_id
        self.slice_index = slice_index - 1  # Convert to 0-based
        
        # Navigate image viewer to the new slice
        self._navigate_to_image()
        
        # Reload the image
        if not self._load_image():
            return
        
        # Reload specimen data for new slice
        self._load_specimen_data()
        
        # Get image dimensions
        img_width = self.current_image.shape[1]
        img_height = self.current_image.shape[0]
        
        # Reset column to center
        self.current_column = img_width // 2
        
        # Update slider range and position
        if hasattr(self, 'slider'):
            self.slider.configure(to=img_width - 1)
            self.slider.set(self.current_column)

        # Update window title
        if self.dialog:
            self.dialog.title(f"A-Scan Viewer - {self.specimen_id} - Slice {self.slice_index + 1}")
        
        # Re-frame the B-scan: the lesion region differs per slice. Done before
        # the indicator, whose canvas position depends on the zoom.
        self._sync_image_analysis_zoom()

        # Update plot (force sync since this is programmatic, not slider drag)
        if hasattr(self, 'ax'):
            self._update_plot(force_image_sync=True)
        
        # Update indicator in image viewer
        self._update_image_indicator()
        
        # Bring window to front
        if self.dialog:
            self.dialog.lift()
            self.dialog.focus_force()
    
    @handle_errors("AScanViewer.on_slice_changed")
    def on_slice_changed(self, new_slice_index, img_width, img_height):
        """Handle slice change from image viewer.
        
        Args:
            new_slice_index: New slice index (0-based)
            img_width: Width of the new image
            img_height: Height of the new image
        """
        # Update slice index
        self.slice_index = new_slice_index
        
        # Reload the image
        if not self._load_image():
            return
        
        # Reload specimen data for new slice
        self._load_specimen_data()
        
        # Reset column to center
        self.current_column = img_width // 2
        
        # Update slider range and position
        if hasattr(self, 'slider'):
            self.slider.configure(to=img_width - 1)
            self.slider.set(self.current_column)

        # Update window title
        if self.dialog:
            self.dialog.title(f"A-Scan Viewer - {self.specimen_id} - Slice {self.slice_index + 1}")
        
        # Re-frame the B-scan: the lesion region differs per slice. Done before
        # the indicator, whose canvas position depends on the zoom.
        self._sync_image_analysis_zoom()

        # Update plot (force sync since this is programmatic, not slider drag)
        if hasattr(self, 'ax'):
            self._update_plot(force_image_sync=True)
        
        # Update indicator in image viewer
        self._update_image_indicator()
    
    def _on_hover(self, event):
        """Handle mouse hover events to show annotation tooltips.
        
        Args:
            event: Matplotlib mouse motion event
        """
        if event.inaxes != self.ax or not self.hover_annotation:
            if self.hover_annotation and self.hover_annotation.get_visible():
                self.hover_annotation.set_visible(False)
                self.figure.canvas.draw_idle()
            return
        
        # Check if mouse is near any annotation point
        hover_threshold = 15  # pixels
        found_point = False
        
        for x, y, label, artist in self.annotation_points:
            # Transform data coordinates to display coordinates
            display_coords = self.ax.transData.transform([[x, y]])[0]
            mouse_coords = np.array([event.x, event.y])
            
            # Calculate distance
            distance = np.sqrt(np.sum((display_coords - mouse_coords) ** 2))
            
            if distance < hover_threshold:
                # Show annotation
                self.hover_annotation.xy = (x, y)
                self.hover_annotation.set_text(label)
                self.hover_annotation.set_visible(True)
                found_point = True
                break
        
        if not found_point and self.hover_annotation.get_visible():
            self.hover_annotation.set_visible(False)
        
        # Force canvas update to ensure annotation visibility changes are rendered
        self.figure.canvas.draw_idle()
    
    def destroy(self):
        """Close the dialog window."""
        if self.dialog:
            self.on_close()
