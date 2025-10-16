#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A-Scan Viewer Module

Provides a non-blocking popup window to display A-Scan data for selected rows.
Displays intensity profile (gray values 0-255) vs depth (y-position) for a column.

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils.error_handler import handle_errors


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
        self.show_knee_point = tk.BooleanVar(value=True)
        self.show_sigmoid_inflection = tk.BooleanVar(value=True)
        self.show_sigmoid_shoulder = tk.BooleanVar(value=True)
        self.show_combined_depth = tk.BooleanVar(value=True)
        self.show_exp2_fit = tk.BooleanVar(value=False)
        self.show_sigmoid_fit = tk.BooleanVar(value=False)
        
        # Cached specimen data
        self.specimen = None
        self.slice_result = None
    
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
        
        # Set size and position
        dialog_width = 900
        dialog_height = 700
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
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
        
        # Toggles frame
        toggles_frame = ttk.LabelFrame(main_frame, text="Display Options", padding=10)
        toggles_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create two rows of checkboxes
        row1 = ttk.Frame(toggles_frame)
        row1.pack(fill=tk.X, pady=(0, 5))
        row2 = ttk.Frame(toggles_frame)
        row2.pack(fill=tk.X)
        
        # Row 1: Surface and depth markers
        ttk.Checkbutton(row1, text="Surface Points", variable=self.show_surface, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row1, text="Knee Point", variable=self.show_knee_point, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row1, text="Sigmoid Inflection", variable=self.show_sigmoid_inflection, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row1, text="Sigmoid Shoulder", variable=self.show_sigmoid_shoulder, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        
        # Row 2: Combined depth and fit curves
        ttk.Checkbutton(row2, text="Combined Depth", variable=self.show_combined_depth, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row2, text="Exp2 Fit Curve", variable=self.show_exp2_fit, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(row2, text="Sigmoid Fit Curve", variable=self.show_sigmoid_fit, 
                       command=self._update_plot).pack(side=tk.LEFT, padx=5)
        
        # Slider frame
        slider_frame = ttk.Frame(main_frame)
        slider_frame.pack(fill=tk.X, pady=(0, 15))
        
        slider_label = ttk.Label(
            slider_frame,
            text="A-Scan Column (X position):",
            font=('Segoe UI', 10)
        )
        slider_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Initialize to middle column
        self.current_column = img_width // 2
        
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=img_width - 1,
            orient=tk.HORIZONTAL,
            command=self._on_slider_change
        )
        self.slider.set(self.current_column)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.column_label = ttk.Label(
            slider_frame,
            text=f"Column: {self.current_column}",
            font=('Segoe UI', 10),
            width=15
        )
        self.column_label.pack(side=tk.LEFT)
        
        # Plot frame
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True)
        
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
        # Create figure with dark background
        self.figure = Figure(figsize=(8, 5), facecolor='#2b2b2b')
        self.ax = self.figure.add_subplot(111)
        
        # Set dark theme for plot
        self.ax.set_facecolor('#1e1e1e')
        self.ax.spines['bottom'].set_color('#dcdcdc')
        self.ax.spines['top'].set_color('#dcdcdc')
        self.ax.spines['left'].set_color('#dcdcdc')
        self.ax.spines['right'].set_color('#dcdcdc')
        self.ax.tick_params(colors='#dcdcdc', which='both')
        self.ax.xaxis.label.set_color('#dcdcdc')
        self.ax.yaxis.label.set_color('#dcdcdc')
        self.ax.title.set_color('#dcdcdc')
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.figure, parent_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial plot
        self._update_plot()
    
    @handle_errors("AScanViewer._update_plot")
    def _update_plot(self):
        """Update the plot with current column data and annotations."""
        if self.current_image is None or self.current_column is None:
            return
        
        # Extract column (A-scan)
        column_data = self.current_image[:, self.current_column]
        
        # Y-axis is depth (0 at top, increasing downward)
        y_positions = np.arange(len(column_data))
        
        # Clear previous plot
        self.ax.clear()
        
        # Plot intensity vs depth (main A-scan line)
        self.ax.plot(column_data, y_positions, color='#00d4ff', linewidth=1.0, label='A-Scan', zorder=1)
        
        # Get surface and lesion depth data for this column
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
        
        # Plot surface points
        if self.show_surface.get():
            if surface_y is not None:
                intensity = column_data[int(surface_y)] if int(surface_y) < len(column_data) else 128
                self.ax.plot(intensity, surface_y, 'o', color='#00ff00', markersize=8, 
                           label='Actual Surface', zorder=5)
            
            if interpolated_surface_y is not None:
                intensity = column_data[int(interpolated_surface_y)] if int(interpolated_surface_y) < len(column_data) else 128
                self.ax.plot(intensity, interpolated_surface_y, 's', color='#00ff88', markersize=8, 
                           label='Interpolated Surface', zorder=5)
        
        # Plot detection method results if available
        if lesion_detection_data:
            metadata = lesion_detection_data.get('detection_metadata', {})
            
            # Knee point
            if self.show_knee_point.get() and 'knee_depth' in metadata:
                knee_depth = metadata['knee_depth']
                if not np.isnan(knee_depth):
                    intensity = column_data[int(knee_depth)] if int(knee_depth) < len(column_data) else 128
                    self.ax.plot(intensity, knee_depth, '^', color='#ff6b6b', markersize=10, 
                               label='Knee Point', zorder=4)
            
            # Sigmoid inflection point
            if self.show_sigmoid_inflection.get() and 'inflection_depth' in metadata:
                inflection_depth = metadata['inflection_depth']
                if not np.isnan(inflection_depth):
                    intensity = column_data[int(inflection_depth)] if int(inflection_depth) < len(column_data) else 128
                    self.ax.plot(intensity, inflection_depth, 'v', color='#ffd93d', markersize=10, 
                               label='Sigmoid Inflection', zorder=4)
            
            # Sigmoid shoulder point
            if self.show_sigmoid_shoulder.get() and 'shoulder_depth' in metadata:
                shoulder_depth = metadata['shoulder_depth']
                if not np.isnan(shoulder_depth):
                    intensity = column_data[int(shoulder_depth)] if int(shoulder_depth) < len(column_data) else 128
                    self.ax.plot(intensity, shoulder_depth, 'd', color='#ff9ff3', markersize=10, 
                               label='Sigmoid Shoulder', zorder=4)
            
            # Combined depth (final result)
            if self.show_combined_depth.get() and 'depth_idx' in lesion_detection_data:
                depth_idx = lesion_detection_data['depth_idx']
                if len(depth_idx) > 0 and not np.isnan(depth_idx[0]):
                    combined_depth = depth_idx[0]
                    intensity = column_data[int(combined_depth)] if int(combined_depth) < len(column_data) else 128
                    self.ax.plot(intensity, combined_depth, '*', color='#ff4757', markersize=15, 
                               label='Combined Depth', zorder=6)
            
            # Plot fit curves
            if 'intensity' in lesion_detection_data:
                intensity_values = lesion_detection_data['intensity']
                
                # Exp2 fit curve
                if self.show_exp2_fit.get() and 'exp2_fit' in metadata:
                    exp2_fit = metadata['exp2_fit']
                    if exp2_fit is not None and len(exp2_fit) == len(intensity_values):
                        y_fit = np.arange(len(exp2_fit))
                        if surface_y is not None:
                            y_fit = y_fit + surface_y
                        self.ax.plot(exp2_fit, y_fit, '--', color='#48dbfb', linewidth=2, 
                                   label='Exp2 Fit', alpha=0.7, zorder=2)
                
                # Sigmoid fit curve
                if self.show_sigmoid_fit.get() and 'sigmoid_fit' in metadata:
                    sigmoid_fit = metadata['sigmoid_fit']
                    if sigmoid_fit is not None and len(sigmoid_fit) == len(intensity_values):
                        y_fit = np.arange(len(sigmoid_fit))
                        if surface_y is not None:
                            y_fit = y_fit + surface_y
                        self.ax.plot(sigmoid_fit, y_fit, '--', color='#feca57', linewidth=2, 
                                   label='Sigmoid Fit', alpha=0.7, zorder=2)
        
        # Set labels and title
        self.ax.set_xlabel('Gray Value (Intensity)', fontsize=11, color='#dcdcdc')
        self.ax.set_ylabel('Depth (Y Position)', fontsize=11, color='#dcdcdc')
        self.ax.set_title(f'A-Scan at Column {self.current_column}', fontsize=12, color='#dcdcdc', pad=10)
        
        # Set limits
        self.ax.set_xlim(0, 255)
        self.ax.set_ylim(len(column_data), 0)  # Invert Y-axis (0 at top)
        
        # Grid
        self.ax.grid(True, alpha=0.2, color='#dcdcdc')
        
        # Legend (only if there are annotations to show)
        handles, labels = self.ax.get_legend_handles_labels()
        if len(handles) > 1:  # More than just the A-Scan line
            self.ax.legend(loc='upper right', fontsize=9, framealpha=0.9, 
                          facecolor='#2b2b2b', edgecolor='#dcdcdc', labelcolor='#dcdcdc')
        
        # Tight layout
        self.figure.tight_layout()
        
        # Redraw
        self.canvas.draw()
    
    @handle_errors("AScanViewer._on_slider_change")
    def _on_slider_change(self, value):
        """Handle slider value change."""
        self.current_column = int(float(value))
        if hasattr(self, 'column_label'):
            self.column_label.config(text=f"Column: {self.current_column}")
        if hasattr(self, 'ax'):
            self._update_plot()
        # Update indicator line in image viewer
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
        # Destroy the dialog
        self.dialog.destroy()
    
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
            self.column_label.config(text=f"Column: {self.current_column}")
        
        # Update window title
        if self.dialog:
            self.dialog.title(f"A-Scan Viewer - {self.specimen_id} - Slice {self.slice_index + 1}")
        
        # Update plot
        if hasattr(self, 'ax'):
            self._update_plot()
        
        # Update indicator in image viewer
        self._update_image_indicator()
    
    def destroy(self):
        """Close the dialog window."""
        if self.dialog:
            self.on_close()
