#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A-Scan Viewer Module

Provides a non-blocking popup window to display A-Scan data for selected rows.
Displays intensity profile (gray values 0-255) vs depth (y-position) for a column.

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils.error_handler import handle_errors
from carlquant_frames.carl_quant_core import fit_exp2_to_profile, detect_depth_sigmoid_fit
from carlquant_frames.annotation_colors import ROW_HIGHLIGHT_NAVIGATION_COLOR


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
        self.show_combined_depth = tk.BooleanVar(value=True)
        self.show_exp2_fit = tk.BooleanVar(value=False)
        self.show_sigmoid_fit = tk.BooleanVar(value=False)
        self.zoom_to_analysis = tk.BooleanVar(value=False)  # Zoom to analysis region
        
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
        dialog_width = 400  # Narrower than before (was 900)
        dialog_height = int(screen_height * 0.75)  # 75% of screen height
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Apply dark theme colors
        bg_color = self.style.colors.bg
        self.dialog.configure(bg=bg_color)
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Get image dimensions for slider range
        img_width = self.current_image.shape[1]
        
        # Load specimen data for annotations
        self._load_specimen_data()
        
        # Toggles frame with grid layout for neat 2-column alignment
        toggles_frame = ttk.LabelFrame(main_frame, text="Display Options", padding=10)
        toggles_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Configure grid columns to distribute evenly
        toggles_frame.columnconfigure(0, weight=1)
        toggles_frame.columnconfigure(1, weight=1)
        
        # Checkboxes in 2 columns using grid
        # Use lambda to ensure slider_dragging is False when checkboxes change
        ttk.Checkbutton(toggles_frame, text="Surface Points", variable=self.show_surface, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=0, column=0, sticky='w', padx=5, pady=2)
        ttk.Checkbutton(toggles_frame, text="Knee Point", variable=self.show_knee_point, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=0, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Checkbutton(toggles_frame, text="Sigmoid Inflection", variable=self.show_sigmoid_inflection, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=1, column=0, sticky='w', padx=5, pady=2)
        ttk.Checkbutton(toggles_frame, text="Sigmoid Shoulder", variable=self.show_sigmoid_shoulder, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=1, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Checkbutton(toggles_frame, text="Combined Depth", variable=self.show_combined_depth, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=2, column=0, sticky='w', padx=5, pady=2)
        ttk.Checkbutton(toggles_frame, text="Exp2 Fit Curve", variable=self.show_exp2_fit, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=2, column=1, sticky='w', padx=5, pady=2)
        
        ttk.Checkbutton(toggles_frame, text="Sigmoid Fit Curve", variable=self.show_sigmoid_fit, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=3, column=0, sticky='w', padx=5, pady=2)
        ttk.Checkbutton(toggles_frame, text="Zoom to Analysis", variable=self.zoom_to_analysis, 
                       command=lambda: self._update_plot(force_image_sync=True)).grid(row=3, column=1, sticky='w', padx=5, pady=2)
        
        # Slider frame with label above
        slider_container = ttk.Frame(main_frame)
        slider_container.pack(fill=tk.X, pady=(0, 15))
        
        # Label above slider
        slider_label = ttk.Label(
            slider_container,
            text="A-Scan",
            font=('Segoe UI', 10, 'bold')
        )
        slider_label.pack(side=tk.TOP, anchor='w', pady=(0, 5))
        
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
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Column number (no "Column:" prefix)
        self.column_label = ttk.Label(
            slider_frame,
            text=f"{self.current_column}",
            font=('Segoe UI', 10),
            width=6
        )
        self.column_label.pack(side=tk.LEFT)
        
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
    
    @handle_errors("AScanViewer._create_plot")
    def _create_plot(self, parent_frame):
        """Create the matplotlib plot for A-Scan visualization."""
        # Create figure with dark background (smaller width for narrow window)
        self.figure = Figure(figsize=(5, 6), facecolor='#2b2b2b')
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
        self.figure.tight_layout()
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
                    'o', '#00ff00', 8, 5)
            
            if interpolated_surface_y is not None:
                intensity = column_data[int(interpolated_surface_y)] if int(interpolated_surface_y) < len(column_data) else 128
                self._plot_point_with_hover(
                    intensity, interpolated_surface_y,
                    f'Interpolated Surface\nX: {intensity:.1f}\nY: {interpolated_surface_y:.1f}',
                    'Interpolated Surface',
                    's', '#00ff88', 8, 5)
        
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
                            '^', '#ff6b6b', 10, 4)
            
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
                            'v', '#ffd93d', 10, 4)
            
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
                            'd', '#ff9ff3', 10, 4)
            
            # Combined depth (final result, relative to surface)
            if self.show_combined_depth.get():
                # Try to get the actual detected depth
                combined_depth = None
                if 'actual_depth' in lesion_detection_data:
                    combined_depth = lesion_detection_data['actual_depth']
                elif 'knee_depth' in lesion_detection_data:
                    combined_depth = lesion_detection_data['knee_depth']
                
                if combined_depth is not None and not np.isnan(combined_depth):
                    absolute_depth = surface_y + combined_depth
                    if int(absolute_depth) < len(column_data):
                        intensity = column_data[int(absolute_depth)]
                        self._plot_point_with_hover(
                            intensity, absolute_depth,
                            f'Combined Depth\nX: {intensity:.1f}\nY: {absolute_depth:.1f}\nDepth: {combined_depth:.1f}px',
                            'Combined Depth',
                            '*', '#ff4757', 15, 6)
            
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
        self.figure.tight_layout()
        
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
        if hasattr(self, 'column_label'):
            self.column_label.config(text=f"{self.current_column}")
        if hasattr(self, 'ax'):
            self._update_plot()  # Will skip image sync during dragging
        # Update indicator line in image viewer (lightweight operation)
        self._update_image_indicator()
    
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
            image_panel.clear_ascan_indicator()
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
        
        # Update column label
        if hasattr(self, 'column_label'):
            self.column_label.config(text=f"{self.current_column}")
        
        # Update window title
        if self.dialog:
            self.dialog.title(f"A-Scan Viewer - {self.specimen_id} - Slice {self.slice_index + 1}")
        
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
        
        # Update column label
        if hasattr(self, 'column_label'):
            self.column_label.config(text=f"{self.current_column}")
        
        # Update window title
        if self.dialog:
            self.dialog.title(f"A-Scan Viewer - {self.specimen_id} - Slice {self.slice_index + 1}")
        
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
