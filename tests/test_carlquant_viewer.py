# -*- coding: utf-8 -*-
"""
Lightweight Image Viewer for CarlQuant Algorithm Testing

This standalone viewer allows you to:
- Load test images from configured specimens
- Navigate through image stacks with a slider
- Visualize algorithm results (surface, regions, lesion depth)
- Compare different algorithm iterations

Created on Mon Oct 06 11:50:00 2025
@author: meissnerto
"""

import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk
import numpy as np
from typing import Dict, Optional
from pathlib import Path
import importlib
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time

# Add parent directory to path so we can import from carlquant_frames
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_carlquant_config import load_test_specimens, load_single_specimen, TestConfig
import test_carlquant_algorithm
from carlquant_frames.specimen_model import Specimen
from carlquant_frames.carl_quant_core import DepthDetectionMethod


# Module-level function for ProcessPoolExecutor (must be picklable)
def process_slice_parallel(slice_idx, image_array, region_config, air_config, num_sound, num_lesion, detection_method="knee_point", compute_all_methods=False, specimen_id="unknown"):
    """
    Process a single slice with pre-loaded image.
    This function must be at module level to be picklable by ProcessPoolExecutor.
    
    Args:
        compute_all_methods: If True, compute all detection methods and store in metadata
        specimen_id: Specimen identifier for logging
    """
    try:
        slice_start = time.time()
        
        # Call algorithm functions directly
        surface = test_carlquant_algorithm.detect_surface(image_array, air_config, region_config)
        region_stats = test_carlquant_algorithm.extract_regions(
            image_array, surface, region_config, num_sound, num_lesion
        )
        # Extract slice ID for logging
        slice_id = f"{specimen_id}_slice{slice_idx}"
        lesion_depth = test_carlquant_algorithm.calculate_lesion_depth(
            surface, region_config, image_array, detection_method=detection_method,
            compute_all_methods=compute_all_methods,
            slice_id=slice_id
        )
        
        slice_time = time.time() - slice_start
        return (slice_idx, region_stats, surface, lesion_depth, None, slice_time)
    except Exception as e:
        import traceback
        return (slice_idx, None, None, None, f"{str(e)}\n{traceback.format_exc()}", 0)


class CarlQuantTestViewer:
    """Lightweight viewer for testing CarlQuant algorithms."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("CarlQuant Algorithm Test Viewer")
        self.root.geometry("1200x800")
        
        # Data
        self.specimens: Dict[str, Specimen] = {}
        self.current_specimen: Optional[Specimen] = None
        self.current_slice_index: int = 0
        self.current_image: Optional[np.ndarray] = None
        self.current_ascan_x: int = 0  # Current A-Scan column position
        
        # Display state
        self.show_surface = tk.BooleanVar(value=True)
        self.show_fitted_curve = tk.BooleanVar(value=True)
        self.show_reference_curve = tk.BooleanVar(value=True)
        self.show_regions = tk.BooleanVar(value=True)
        self.show_air = tk.BooleanVar(value=True)
        self.show_lesion_depth = tk.BooleanVar(value=True)
        self.show_raw_depth = tk.BooleanVar(value=False)  # Show raw knee points
        self.show_ascan = tk.BooleanVar(value=True)
        
        # Detection method selection
        self.detection_method_var = tk.StringVar(value="knee_point")
        self.compare_methods = tk.BooleanVar(value=False)  # Compare all methods
        
        # Results cache
        self.results_cache = {}  # (specimen_id, slice_idx) -> (region_stats, surface, lesion_depth)
        
        self.setup_ui()
        self.load_test_data()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel: Controls
        left_panel = ttk.Frame(main_frame, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Right panel: Image and A-Scan display
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.setup_control_panel(left_panel)
        self.setup_image_panel(right_panel)
    
    def setup_control_panel(self, parent):
        """Setup the control panel with specimen selection and options."""
        # Title
        title_label = ttk.Label(parent, text="Test Viewer Controls", font=("Arial", 12, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Specimen selection
        specimen_frame = ttk.LabelFrame(parent, text="Specimen Selection", padding=10)
        specimen_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.specimen_listbox = tk.Listbox(specimen_frame, height=8)
        self.specimen_listbox.pack(fill=tk.BOTH, expand=True)
        self.specimen_listbox.bind("<<ListboxSelect>>", self.on_specimen_select)
        
        # Buttons
        btn_frame = ttk.Frame(specimen_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(btn_frame, text="Reload", command=self.load_test_data).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Add Path", command=self.add_test_path).pack(side=tk.LEFT)
        
        # Slice navigation
        nav_frame = ttk.LabelFrame(parent, text="Slice Navigation", padding=10)
        nav_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.slice_label = ttk.Label(nav_frame, text="Slice: 0 / 0")
        self.slice_label.pack()
        
        self.slice_scale = ttk.Scale(nav_frame, from_=1, to=1, orient=tk.HORIZONTAL,
                                     command=self.on_slice_change)
        self.slice_scale.pack(fill=tk.X, pady=(5, 0))
        
        # Navigation buttons
        nav_btn_frame = ttk.Frame(nav_frame)
        nav_btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(nav_btn_frame, text="◄ Prev", command=self.prev_slice).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(nav_btn_frame, text="Next ►", command=self.next_slice).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        
        # Algorithm controls
        algo_frame = ttk.LabelFrame(parent, text="Algorithm Settings", padding=10)
        algo_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(algo_frame, text="Number of Regions:").pack(anchor=tk.W)
        self.num_regions_var = tk.IntVar(value=6)
        regions_spin = ttk.Spinbox(algo_frame, from_=2, to=10, textvariable=self.num_regions_var, width=10)
        regions_spin.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(algo_frame, text="(Sound: half, Lesion: all)", font=("Arial", 8)).pack(anchor=tk.W, pady=(0, 5))
        
        # Lesion depth detection method
        ttk.Label(algo_frame, text="Depth Detection Method:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5, 2))
        
        methods_frame = ttk.Frame(algo_frame)
        methods_frame.pack(fill=tk.X, pady=(0, 5))
        
        method_options = [
            ("Knee Point (exp2)", "knee_point"),
            ("Sigmoid Inflection", "sigmoid_fit"),
            ("Sigmoid Shoulder", "sigmoid_shoulder"),
            ("Combined (Mean)", "combined_mean")
        ]
        
        for label, value in method_options:
            ttk.Radiobutton(methods_frame, text=label, 
                          variable=self.detection_method_var, value=value).pack(anchor=tk.W, padx=(10, 0))
        
        ttk.Checkbutton(algo_frame, text="Compare All Methods (A-Scan plot)", 
                       variable=self.compare_methods).pack(anchor=tk.W, pady=(5, 0))
        
        # Parallel processing mode
        parallel_frame = ttk.Frame(algo_frame)
        parallel_frame.pack(fill=tk.X, pady=(5, 2))
        ttk.Label(parallel_frame, text="Processing Mode:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        
        self.parallel_mode_var = tk.StringVar(value="auto")
        ttk.Radiobutton(parallel_frame, text="Auto (parallel if >10 slices)", 
                       variable=self.parallel_mode_var, value="auto").pack(anchor=tk.W, padx=(10, 0))
        ttk.Radiobutton(parallel_frame, text="Always Sequential", 
                       variable=self.parallel_mode_var, value="sequential").pack(anchor=tk.W, padx=(10, 0))
        ttk.Radiobutton(parallel_frame, text="Always Parallel", 
                       variable=self.parallel_mode_var, value="parallel").pack(anchor=tk.W, padx=(10, 0))
        
        # Worker count
        worker_frame = ttk.Frame(algo_frame)
        worker_frame.pack(fill=tk.X, pady=(2, 5))
        ttk.Label(worker_frame, text="Workers (if parallel):", font=("Arial", 8)).pack(side=tk.LEFT)
        self.num_workers_var = tk.IntVar(value=max(1, multiprocessing.cpu_count() - 1))
        ttk.Spinbox(worker_frame, from_=1, to=multiprocessing.cpu_count(), 
                   textvariable=self.num_workers_var, width=5).pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Button(algo_frame, text="Run Algorithm", command=self.run_algorithm).pack(fill=tk.X, pady=(5, 0))
        ttk.Button(algo_frame, text="Clear Cache", command=self.clear_cache).pack(fill=tk.X, pady=(5, 0))
        
        # Display options
        display_frame = ttk.LabelFrame(parent, text="Display Options", padding=10)
        display_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(display_frame, text="Show Surface Peaks", variable=self.show_surface,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Fitted Curve (Primary)", variable=self.show_fitted_curve,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Reference Curve", variable=self.show_reference_curve,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Regions", variable=self.show_regions,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show AIR", variable=self.show_air,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Lesion Depth (Smoothed)", variable=self.show_lesion_depth,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Raw Depth Points", variable=self.show_raw_depth,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show A-Scan", variable=self.show_ascan,
                       command=self.update_display).pack(anchor=tk.W)
        
        # Info panel
        info_frame = ttk.LabelFrame(parent, text="Information", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_text = tk.Text(info_frame, height=10, wrap=tk.WORD, font=("Courier", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar for info
        info_scroll = ttk.Scrollbar(info_frame, command=self.info_text.yview)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.config(yscrollcommand=info_scroll.set)
    
    def setup_image_panel(self, parent):
        """Setup the image display panel with A-Scan viewer."""
        # Main container with image on left and A-Scan plot on right
        display_container = ttk.Frame(parent)
        display_container.pack(fill=tk.BOTH, expand=True)
        
        # Left side: Image display
        image_frame = ttk.Frame(display_container)
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas for image display
        self.canvas = tk.Canvas(image_frame, bg='#2b2b2b', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # A-Scan position slider (below image)
        ascan_frame = ttk.Frame(image_frame)
        ascan_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.ascan_label = ttk.Label(ascan_frame, text="A-Scan X: 0")
        self.ascan_label.pack()
        
        self.ascan_scale = ttk.Scale(ascan_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                     command=self.on_ascan_change)
        self.ascan_scale.pack(fill=tk.X)
        
        # Right side: A-Scan intensity plot
        plot_frame = ttk.Frame(display_container, width=300)
        plot_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        plot_frame.pack_propagate(False)
        
        ttk.Label(plot_frame, text="A-Scan Intensity Profile", font=("Arial", 10, "bold")).pack(pady=(0, 5))
        
        self.plot_canvas = tk.Canvas(plot_frame, bg='white', highlightthickness=1, highlightbackground='gray')
        self.plot_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_label = ttk.Label(parent, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, pady=(5, 0))
    
    def load_test_data(self):
        """Load test specimens from configured paths."""
        self.specimens = load_test_specimens()
        
        # Update listbox
        self.specimen_listbox.delete(0, tk.END)
        for specimen_id in sorted(self.specimens.keys()):
            self.specimen_listbox.insert(tk.END, specimen_id)
        
        if self.specimens:
            self.update_info(f"Loaded {len(self.specimens)} test specimen(s)")
        else:
            self.update_info("No test specimens found. Add paths using 'Add Path' button.")
    
    def add_test_path(self):
        """Add a new test data path."""
        path = filedialog.askdirectory(title="Select Test Data Folder")
        if path:
            if TestConfig.add_test_path(path):
                self.load_test_data()
                self.update_info(f"Added test path: {path}")
            else:
                messagebox.showwarning("Invalid Path", "Path does not exist or already added.")
    
    def on_specimen_select(self, event):
        """Handle specimen selection."""
        selection = self.specimen_listbox.curselection()
        if not selection:
            return
        
        specimen_id = self.specimen_listbox.get(selection[0])
        self.current_specimen = self.specimens[specimen_id]
        self.current_slice_index = 0
        
        # Update slice scale
        num_slices = len(self.current_specimen.images)
        self.slice_scale.config(from_=1, to=num_slices)
        self.slice_scale.set(1)
        
        # Display first slice
        self.display_slice(0)
        
        # Update info
        info = f"Specimen: {specimen_id}\n"
        info += f"Slices: {num_slices}\n"
        if self.current_specimen.config:
            info += f"Regions configured: {len(self.current_specimen.config.regions)}\n"
            info += f"AIR configured: {len(self.current_specimen.config.air)}\n"
        else:
            info += "WARNING: No configuration found!\n"
        
        self.update_info(info)
    
    def on_slice_change(self, value):
        """Handle slice scale change."""
        if self.current_specimen is None:
            return
        
        slice_idx = int(float(value)) - 1
        self.display_slice(slice_idx)
    
    def prev_slice(self):
        """Navigate to previous slice."""
        if self.current_specimen is None:
            return
        
        current = int(self.slice_scale.get())
        if current > 1:
            self.slice_scale.set(current - 1)
    
    def next_slice(self):
        """Navigate to next slice."""
        if self.current_specimen is None:
            return
        
        current = int(self.slice_scale.get())
        max_slice = len(self.current_specimen.images)
        if current < max_slice:
            self.slice_scale.set(current + 1)
    
    def display_slice(self, slice_idx: int):
        """Display a specific slice."""
        if self.current_specimen is None:
            return
        
        self.current_slice_index = slice_idx
        
        # Load image
        image_path = self.current_specimen.images[slice_idx]
        img = Image.open(image_path).convert('L')
        self.current_image = np.array(img)
        
        # Update A-Scan scale range
        width = self.current_image.shape[1]
        self.ascan_scale.config(from_=0, to=width-1)
        if self.current_ascan_x >= width:
            self.current_ascan_x = width // 2
        self.ascan_scale.set(self.current_ascan_x)
        
        # Update label
        self.slice_label.config(text=f"Slice: {slice_idx + 1} / {len(self.current_specimen.images)}")
        
        # Display with overlays
        self.update_display()
    
    def on_ascan_change(self, value):
        """Handle A-Scan position change."""
        if self.current_image is None:
            return
        
        self.current_ascan_x = int(float(value))
        self.ascan_label.config(text=f"A-Scan X: {self.current_ascan_x}")
        self.update_display()
    
    def update_display(self):
        """Update the canvas display with current image and overlays."""
        if self.current_image is None:
            return
        
        # Update info panel for current slice
        self.update_slice_info()
        
        # Start with grayscale image
        display_image = self.current_image.copy()
        
        # Convert to RGB for overlays
        if len(display_image.shape) == 2:
            display_image = np.stack([display_image] * 3, axis=-1)
        
        # Draw A-Scan vertical line
        if self.show_ascan.get() and 0 <= self.current_ascan_x < display_image.shape[1]:
            display_image[:, self.current_ascan_x] = [255, 0, 255]  # Magenta line
        
        # Check if we have results for this slice
        cache_key = (self.current_specimen.specimen_id, self.current_slice_index)
        if cache_key in self.results_cache:
            region_stats, surface, lesion_depth = self.results_cache[cache_key]
            
            # Draw interpolated surface curve first (cyan) - bottom layer
            if self.show_reference_curve.get() and surface:
                if surface.fitted_curves and "interpolated_surface" in surface.fitted_curves:
                    for x, y in surface.fitted_curves["interpolated_surface"]:
                        if 0 <= x < display_image.shape[1] and 0 <= y < display_image.shape[0]:
                            # Draw thicker line (3 pixels vertical thickness)
                            for dy in range(-1, 2):
                                ny = y + dy
                                if 0 <= ny < display_image.shape[0]:
                                    display_image[ny, x] = [0, 255, 255]  # Cyan
            
            # Draw actual surface curve (orange) with thickness - middle layer
            if self.show_fitted_curve.get() and surface:
                if surface.fitted_curves and "actual_surface" in surface.fitted_curves:
                    for x, y in surface.fitted_curves["actual_surface"]:
                        if 0 <= x < display_image.shape[1] and 0 <= y < display_image.shape[0]:
                            # Draw thicker line (3 pixels vertical thickness)
                            for dy in range(-1, 2):
                                ny = y + dy
                                if 0 <= ny < display_image.shape[0]:
                                    display_image[ny, x] = [255, 165, 0]  # Orange
            
            # Draw detected surface peaks (green) - top layer
            if self.show_surface.get() and surface:
                for idx, (x, y) in enumerate(surface.raw_points):
                    if 0 <= x < display_image.shape[1] and 0 <= y < display_image.shape[0]:
                        # Green color for detected peaks
                        color = [0, 255, 0]  # Green - Surface peaks
                        
                        # Draw a small cross
                        for dx in range(-2, 3):
                            for dy in range(-2, 3):
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < display_image.shape[1] and 0 <= ny < display_image.shape[0]:
                                    if abs(dx) <= 1 or abs(dy) <= 1:
                                        display_image[ny, nx] = color
        
        # Draw region boundaries (4 vertical lines)
        # Green for specimen boundaries, Yellow for lesion boundaries
        if self.show_regions.get() and self.current_specimen.config:
            if self.current_slice_index in self.current_specimen.config.regions:
                region = self.current_specimen.config.regions[self.current_slice_index]
                
                # Define 4 boundaries with colors
                boundaries = [
                    (region.specimen_start[0], [0, 255, 0]),      # Green - Specimen Start
                    (region.lesion_start[0], [255, 255, 0]),      # Yellow - Lesion Start
                    (region.lesion_end[0], [255, 255, 0]),        # Yellow - Lesion End
                    (region.tooth_end[0], [0, 255, 0])            # Green - Tooth End
                ]
                
                # Draw vertical lines
                for x, color in boundaries:
                    if 0 <= x < display_image.shape[1]:
                        display_image[:, x] = color
        
        # Draw AIR region
        if self.show_air.get() and self.current_specimen.config:
            if self.current_slice_index in self.current_specimen.config.air:
                air = self.current_specimen.config.air[self.current_slice_index]
                if air.point2:
                    x1, y1 = air.point1
                    x2, y2 = air.point2
                    
                    # Draw rectangle
                    for x in range(max(0, x1), min(display_image.shape[1], x2)):
                        if 0 <= y1 < display_image.shape[0]:
                            display_image[y1, x] = [0, 255, 255]  # Cyan
                        if 0 <= y2 < display_image.shape[0]:
                            display_image[y2, x] = [0, 255, 255]  # Cyan
                    for y in range(max(0, y1), min(display_image.shape[0], y2)):
                        if 0 <= x1 < display_image.shape[1]:
                            display_image[y, x1] = [0, 255, 255]  # Cyan
                        if 0 <= x2 < display_image.shape[1]:
                            display_image[y, x2] = [0, 255, 255]  # Cyan
        
        # Draw extraction regions (rectangles with numbers)
        if self.show_regions.get() and cache_key in self.results_cache:
            region_stats, _, _ = self.results_cache[cache_key]
            
            # Convert to PIL Image for drawing
            pil_image = Image.fromarray(display_image)
            draw = ImageDraw.Draw(pil_image)
            
            # Try to load a font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            for stats in region_stats:
                if stats.bounds and len(stats.bounds) > 0:
                    # Choose color based on region type
                    if stats.region_type == "sound":
                        color_rgb = (0, 255, 0)  # Green for sound
                    else:
                        color_rgb = (255, 0, 0)  # Red for lesion
                    
                    # Check if we have rotated corners (4 points) or simple bbox (4 values)
                    if len(stats.bounds) == 4 and isinstance(stats.bounds[0], tuple):
                        # Rotated rectangle with 4 corner points
                        corners = stats.bounds
                        
                        # Draw polygon outline
                        draw.polygon(corners, outline=color_rgb, width=1)
                        
                        # Calculate center from corners
                        center_x = sum(x for x, y in corners) // 4
                        center_y = sum(y for x, y in corners) // 4
                        
                    else:
                        # Simple axis-aligned rectangle
                        left_x, top_y, right_x, bottom_y = stats.bounds
                        
                        # Draw rectangle outline
                        draw.rectangle(
                            [(left_x, top_y), (right_x - 1, bottom_y - 1)],
                            outline=color_rgb,
                            width=1
                        )
                        
                        center_x = (left_x + right_x) // 2
                        center_y = (top_y + bottom_y) // 2
                    
                    # Draw region number in center (rotated if needed)
                    text = str(stats.region_index)
                    
                    # Get text size for centering
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Create rotated text if rotation angle is significant
                    if hasattr(stats, 'rotation_angle') and abs(stats.rotation_angle) > 1:
                        # Create a temporary image for rotated text
                        text_img = Image.new('RGBA', (text_width + 10, text_height + 10), (0, 0, 0, 0))
                        text_draw = ImageDraw.Draw(text_img)
                        text_draw.text((5, 5), text, fill=color_rgb + (255,), font=font)
                        
                        # Rotate text
                        rotated_text = text_img.rotate(-stats.rotation_angle, expand=True, fillcolor=(0, 0, 0, 0))
                        
                        # Paste rotated text at center
                        paste_x = center_x - rotated_text.width // 2
                        paste_y = center_y - rotated_text.height // 2
                        pil_image.paste(rotated_text, (paste_x, paste_y), rotated_text)
                    else:
                        # Draw unrotated text
                        text_x = center_x - text_width // 2
                        text_y = center_y - text_height // 2
                        draw.text((text_x, text_y), text, fill=color_rgb, font=font)
            
            # Convert back to numpy array
            display_image = np.array(pil_image)
        
        # Draw single-method results (only when NOT in comparison mode)
        if not self.compare_methods.get() and cache_key in self.results_cache:
            _, _, lesion_depth = self.results_cache[cache_key]
            
            # Draw lesion depth (raw knee points - small markers)
            if self.show_raw_depth.get() and lesion_depth and lesion_depth.depth_points:
                for x, depth in lesion_depth.depth_points:
                    if 0 <= x < display_image.shape[1]:
                        # Draw small cross marker for raw points
                        y = int(depth)
                        if 0 <= y < display_image.shape[0]:
                            # Draw cross pattern
                            for dx in range(-1, 2):
                                nx = x + dx
                                if 0 <= nx < display_image.shape[1]:
                                    display_image[y, nx] = [255, 255, 0]  # Yellow for raw
                            for dy in range(-1, 2):
                                ny = y + dy
                                if 0 <= ny < display_image.shape[0]:
                                    display_image[ny, x] = [255, 255, 0]  # Yellow for raw
            
            # Draw smoothed lesion depth (spline-fitted curve - thicker line)
            if self.show_lesion_depth.get() and lesion_depth and lesion_depth.smoothed_depth_points:
                # Draw smoothed curve with thickness
                for x, depth in lesion_depth.smoothed_depth_points:
                    if 0 <= x < display_image.shape[1]:
                        # Draw thicker line (3 pixels vertical thickness)
                        for dy in range(-1, 2):
                            y = int(depth) + dy
                            if 0 <= y < display_image.shape[0]:
                                display_image[y, x] = [0, 255, 0]  # Green for smoothed
        
        # Draw method comparison on image if enabled
        if self.compare_methods.get() and cache_key in self.results_cache:
            _, surface, lesion_depth = self.results_cache[cache_key]
            if lesion_depth and lesion_depth.lesion_detection_data and surface.fitted_curves and "actual_surface" in surface.fitted_curves:
                # OPTIMIZED: No status update needed - drawing is now fast!
                self.draw_method_comparison_on_image(display_image, lesion_depth, surface)
                
                # Add legend for comparison mode
                pil_temp = Image.fromarray(display_image.astype(np.uint8))
                draw = ImageDraw.Draw(pil_temp)
                
                # Try to load a font
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                
                # Legend position (top-left corner)
                legend_x = 10
                legend_y = 10
                line_height = 15
                
                # Define legend entries based on what's visible
                legend_entries = [
                    ("Red: Knee Point", (255, 0, 0)),
                    ("Purple: Sigmoid Inflection", (128, 0, 128)),
                    ("Cyan: Sigmoid Shoulder", (0, 255, 255))
                ]
                
                # Add combined mean if it exists in the results
                if hasattr(lesion_depth, 'method_splines') and lesion_depth.method_splines:
                    if 'combined_mean' in lesion_depth.method_splines:
                        legend_entries.append(("Yellow: Combined Mean", (255, 255, 0)))
                
                # Draw legend background (semi-transparent black)
                legend_width = 200
                legend_height = len(legend_entries) * line_height + 10
                for y in range(legend_y, legend_y + legend_height):
                    for x in range(legend_x, legend_x + legend_width):
                        if 0 <= x < display_image.shape[1] and 0 <= y < display_image.shape[0]:
                            # Blend with existing pixel (50% transparency)
                            display_image[y, x] = display_image[y, x] // 2
                
                # Draw legend text
                for i, (text, color) in enumerate(legend_entries):
                    y_pos = legend_y + 5 + i * line_height
                    draw.text((legend_x + 5, y_pos), text, fill=color, font=font)
                
                display_image = np.array(pil_temp)
        
        # Convert to PIL and display
        pil_image = Image.fromarray(display_image.astype(np.uint8))
        
        # Resize to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width > 1 and canvas_height > 1:
            # Calculate scaling to fit
            scale = min(canvas_width / pil_image.width, canvas_height / pil_image.height)
            new_width = int(pil_image.width * scale)
            new_height = int(pil_image.height * scale)
            pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
        
        # Display on canvas
        self.photo = ImageTk.PhotoImage(pil_image)
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, anchor=tk.CENTER)
        
        # Update A-Scan plot
        self.update_ascan_plot()
    
    def run_algorithm(self):
        """Run the CarlQuant algorithm on all slices (with optional parallelization)."""
        if self.current_specimen is None or self.current_specimen.config is None:
            messagebox.showwarning("No Configuration", "Please select a specimen with configuration.")
            return
        
        self.update_info("Reloading algorithm module...")
        self.status_label.config(text="Reloading...")
        self.root.update()
        
        try:
            # Hot-reload the algorithm module to pick up changes
            importlib.reload(test_carlquant_algorithm)
            
            # Get settings
            num_slices = len(self.current_specimen.images)
            num_regions = self.num_regions_var.get()
            num_sound = num_regions // 2
            num_lesion = num_regions
            parallel_mode = self.parallel_mode_var.get()
            num_workers = self.num_workers_var.get()
            detection_method = self.detection_method_var.get()
            
            # Prepare slice tasks (only for slices with configuration)
            slice_tasks = []
            for slice_idx in range(num_slices):
                if slice_idx in self.current_specimen.config.regions:
                    region_config = self.current_specimen.config.regions[slice_idx]
                    air_config = self.current_specimen.config.air.get(slice_idx)
                    image_path = self.current_specimen.images[slice_idx]
                    slice_tasks.append((slice_idx, image_path, region_config, air_config))
            
            # Determine if we should use parallel processing
            if parallel_mode == "auto":
                use_parallel = len(slice_tasks) > 10
            elif parallel_mode == "parallel":
                use_parallel = True
            else:  # sequential
                use_parallel = False
            
            if len(slice_tasks) == 0:
                messagebox.showwarning("No Configuration", "No slices have region configuration.")
                return
            
            start_time = time.time()
            processed_count = 0
            
            if use_parallel and num_workers > 1:
                # PARALLEL PROCESSING WITH PRE-LOADING (ProcessPoolExecutor)
                # Limit workers to number of slices (no point having more workers than tasks)
                effective_workers = min(num_workers, len(slice_tasks))
                
                print(f"Using parallel processing: {len(slice_tasks)} slices, {effective_workers} workers")
                
                # PRE-LOAD ALL IMAGES INTO MEMORY
                self.status_label.config(text=f"Pre-loading {len(slice_tasks)} images...")
                self.root.update_idletasks()
                
                preload_start = time.time()
                preloaded_images = {}
                for slice_idx, image_path, region_config, air_config in slice_tasks:
                    img = Image.open(image_path).convert('L')
                    preloaded_images[slice_idx] = np.array(img)
                preload_time = time.time() - preload_start
                
                print(f"Pre-loaded {len(preloaded_images)} images in {preload_time:.2f}s")
                
                # Determine if we should compute all methods (for comparison)
                compute_all_methods = self.compare_methods.get()
                
                self.status_label.config(text=f"Processing {len(slice_tasks)} slices using {effective_workers} workers...")
                self.root.update_idletasks()
                
                # Process in parallel using ProcessPoolExecutor
                with ProcessPoolExecutor(max_workers=effective_workers) as executor:
                    # Submit tasks with pre-loaded images
                    future_to_slice = {}
                    for slice_idx, image_path, region_config, air_config in slice_tasks:
                        image_array = preloaded_images[slice_idx]
                        future = executor.submit(
                            process_slice_parallel,
                            slice_idx, image_array, region_config, air_config, num_sound, num_lesion, detection_method, compute_all_methods, self.current_specimen.specimen_id
                        )
                        future_to_slice[future] = slice_idx
                    
                    slice_times = []
                    for future in as_completed(future_to_slice):
                        slice_idx = future_to_slice[future]
                        try:
                            result_idx, region_stats, surface, lesion_depth, error, slice_time = future.result()
                            
                            if error:
                                print(f"Error processing slice {result_idx}: {error}")
                            else:
                                slice_times.append(slice_time)
                                # Cache results
                                cache_key = (self.current_specimen.specimen_id, result_idx)
                                self.results_cache[cache_key] = (region_stats, surface, lesion_depth)
                                processed_count += 1
                                
                                # Update UI periodically
                                if processed_count % 5 == 0 or processed_count == len(slice_tasks):
                                    self.status_label.config(text=f"Processed {processed_count}/{len(slice_tasks)}...")
                                    self.root.update_idletasks()
                        except Exception as e:
                            print(f"Exception processing slice {slice_idx}: {e}")
                
                # Calculate elapsed time for parallel
                elapsed_time = time.time() - start_time
                
                # Print timing analysis
                if slice_times:
                    avg_slice_time = sum(slice_times) / len(slice_times)
                    processing_time = elapsed_time - preload_time
                    print(f"\n=== PARALLEL TIMING (PROCESSES, WITH PRE-LOADING) ===")
                    print(f"Pre-load time: {preload_time:.2f}s")
                    print(f"Processing time: {processing_time:.2f}s")
                    print(f"Total wall time: {elapsed_time:.2f}s")
                    print(f"Avg slice time: {avg_slice_time:.2f}s")
                    print(f"Sum of slice times: {sum(slice_times):.2f}s")
                    print(f"Theoretical speedup: {sum(slice_times) / processing_time:.2f}x")
                    print(f"Overhead: {processing_time - max(slice_times):.2f}s")
            
            else:
                # SEQUENTIAL PROCESSING
                # Determine if we should compute all methods (for comparison)
                compute_all_methods = self.compare_methods.get()
                
                print(f"Using sequential processing: {len(slice_tasks)} slices")
                self.status_label.config(text=f"Processing {len(slice_tasks)} slices sequentially...")
                self.root.update_idletasks()
                
                slice_times = []
                for i, task in enumerate(slice_tasks):
                    slice_idx, image_path, region_config, air_config = task
                    
                    try:
                        slice_start = time.time()
                        region_stats, surface, lesion_depth = test_carlquant_algorithm.process_slice(
                            image_path, region_config, air_config, num_sound, num_lesion, detection_method, compute_all_methods
                        )
                        slice_time = time.time() - slice_start
                        slice_times.append(slice_time)
                        
                        # Cache results
                        cache_key = (self.current_specimen.specimen_id, slice_idx)
                        self.results_cache[cache_key] = (region_stats, surface, lesion_depth)
                        processed_count += 1
                        
                        # Update UI periodically
                        if (i + 1) % 5 == 0 or (i + 1) == len(slice_tasks):
                            self.status_label.config(text=f"Processing {i + 1}/{len(slice_tasks)}...")
                            self.root.update_idletasks()
                    
                    except Exception as e:
                        print(f"Error processing slice {slice_idx}: {e}")
                
                # Calculate elapsed time for sequential
                elapsed_time = time.time() - start_time
                
                # Print timing analysis
                if slice_times:
                    avg_slice_time = sum(slice_times) / len(slice_times)
                    print(f"\n=== SEQUENTIAL TIMING ===")
                    print(f"Total time: {elapsed_time:.2f}s")
                    print(f"Avg slice time: {avg_slice_time:.2f}s")
                    print(f"Min slice time: {min(slice_times):.2f}s")
                    print(f"Max slice time: {max(slice_times):.2f}s")
            
            # Update status and display
            if use_parallel and num_workers > 1:
                effective_workers = min(num_workers, len(slice_tasks))
                mode_str = f"parallel ({effective_workers} workers)"
            else:
                mode_str = "sequential"
            
            self.status_label.config(
                text=f"Completed: {processed_count} slices in {elapsed_time:.1f}s ({mode_str})"
            )
            
            # Update display (which will automatically update info panel)
            self.update_display()
            
        except Exception as e:
            messagebox.showerror("Algorithm Error", f"Error running algorithm:\n{str(e)}")
            self.status_label.config(text="Error")
            import traceback
            traceback.print_exc()
    
    def draw_method_comparison_on_image(self, display_image, lesion_depth, surface):
        """Draw all detection methods' results on the main image with smoothed splines.
        
        Uses pre-computed splines from lesion_depth.method_splines if available (fast!).
        Falls back to on-the-fly computation if not available (slower, backward compatible).
        """
        from carlquant_frames.carl_quant_core import (
            detect_depth_sigmoid_fit,
            knee_pt,
            fit_exp2_to_profile
        )
        from test_carlquant_algorithm import fit_surface_curve
        
        # Get surface dictionary
        surface_dict = {x: y for x, y in surface.fitted_curves["actual_surface"]}
        
        # Method colors (RGB) - using distinct colors for visibility
        method_colors = {
            "knee_point": [255, 0, 0],      # Red
            "sigmoid_fit": [128, 0, 128],   # Purple
            "sigmoid_shoulder": [0, 255, 255],  # Cyan
            "combined_mean": [255, 255, 0]  # Yellow - for stability-based combined result
        }
        
        # Check if we have pre-computed splines (FAST PATH - OPTIMIZED)
        if hasattr(lesion_depth, 'method_splines') and lesion_depth.method_splines:
            # Use pre-computed splines - no computation needed!
            for method_name, smoothed_points in lesion_depth.method_splines.items():
                # Skip non-spline entries (like stability_info)
                if method_name == 'stability_info':
                    continue
                if method_name in method_colors:
                    color = method_colors[method_name]
                    
                    # Only draw smoothed splines if "Show Lesion Depth (Smoothed)" is enabled
                    # OR if "Show Raw Depth Points" is disabled (default behavior)
                    if not self.show_lesion_depth.get() and not self.show_raw_depth.get():
                        # Default: show smoothed splines when neither toggle is explicitly set
                        pass  # Continue to draw
                    elif not self.show_lesion_depth.get():
                        # User explicitly disabled smoothed depth
                        continue  # Skip this spline
                    
                    # OPTIMIZED: Vectorized drawing of smoothed spline (3-pixel thickness)
                    if len(smoothed_points) > 0:
                        # Convert to numpy arrays for vectorized operations
                        points_array = np.array(smoothed_points, dtype=np.int32)
                        x_coords = points_array[:, 0]
                        y_coords = points_array[:, 1]
                        
                        # Filter valid coordinates
                        valid_mask = (x_coords >= 0) & (x_coords < display_image.shape[1]) & \
                                    (y_coords >= 0) & (y_coords < display_image.shape[0])
                        x_valid = x_coords[valid_mask]
                        y_valid = y_coords[valid_mask]
                        
                        # Draw with 3-pixel thickness (center + above + below)
                        for dy in [-1, 0, 1]:
                            y_offset = y_valid + dy
                            # Additional bounds check for offset
                            offset_valid = (y_offset >= 0) & (y_offset < display_image.shape[0])
                            display_image[y_offset[offset_valid], x_valid[offset_valid]] = color
                    
                    # Draw raw points if toggle is enabled (OPTIMIZED)
                    if self.show_raw_depth.get() and lesion_depth.lesion_detection_data:
                        # Determine depth key for this method
                        depth_key_map = {
                            "knee_point": 'knee_depth',
                            "sigmoid_fit": 'inflection_depth',
                            "sigmoid_shoulder": 'shoulder_depth'
                        }
                        depth_key = depth_key_map.get(method_name)
                        
                        if depth_key:
                            # Collect all valid raw points for this method
                            raw_points = []
                            for x, detection_info in lesion_depth.lesion_detection_data.items():
                                if x not in surface_dict:
                                    continue
                                surface_y = detection_info['surface_y']
                                metadata = detection_info.get('detection_metadata', {})
                                
                                if depth_key in metadata:
                                    depth = metadata[depth_key]
                                    if not np.isnan(depth):
                                        abs_y = int(surface_y + depth)
                                        if 0 <= abs_y < display_image.shape[0]:
                                            raw_points.append((x, abs_y))
                            
                            # Vectorized drawing of raw point markers (3x3 squares)
                            if len(raw_points) > 0:
                                raw_array = np.array(raw_points, dtype=np.int32)
                                for dx in [-1, 0, 1]:
                                    for dy in [-1, 0, 1]:
                                        x_offset = raw_array[:, 0] + dx
                                        y_offset = raw_array[:, 1] + dy
                                        # Bounds check
                                        valid = (x_offset >= 0) & (x_offset < display_image.shape[1]) & \
                                               (y_offset >= 0) & (y_offset < display_image.shape[0])
                                        display_image[y_offset[valid], x_offset[valid]] = color
            return  # Done! No need for fallback computation
        
        # Collect raw depth data for each method
        method_raw_depths = {
            "knee_point": [],
            "sigmoid_fit": [],
            "sigmoid_shoulder": []
        }
        
        # Process each column to collect raw depth points
        for x, detection_info in lesion_depth.lesion_detection_data.items():
            if x not in surface_dict:
                continue
            
            surface_y = detection_info['surface_y']
            detection_metadata = detection_info.get('detection_metadata', {})
            
            # Get intensity profile for computing missing methods
            intensity_profile = np.array(detection_info['intensity'])
            depth_idx = np.array(detection_info['depth_idx'])
            
            # Extract or compute knee point depth
            if 'knee_depth' in detection_info:
                knee_depth = detection_info['knee_depth']
            else:
                # Compute knee point if not available
                try:
                    fit_result = fit_exp2_to_profile(intensity_profile, depth_idx)
                    if fit_result is not None:
                        fitted_curve, _ = fit_result
                        knee_depth, _ = knee_pt(fitted_curve, depth_idx)
                    else:
                        knee_depth, _ = knee_pt(intensity_profile, depth_idx)
                except:
                    knee_depth = np.nan
            
            if not np.isnan(knee_depth):
                abs_y = int(surface_y + knee_depth)
                if 0 <= abs_y < display_image.shape[0]:
                    method_raw_depths["knee_point"].append((x, abs_y))
            
            # Extract or compute sigmoid depths
            if 'inflection_depth' in detection_metadata and 'shoulder_depth' in detection_metadata:
                # Already computed - use stored values
                inflection_depth = detection_metadata.get('inflection_depth')
                shoulder_depth = detection_metadata.get('shoulder_depth')
            else:
                # Compute sigmoid if not available
                try:
                    _, _, sigmoid_meta = detect_depth_sigmoid_fit(intensity_profile, depth_idx)
                    if sigmoid_meta.get('success'):
                        inflection_depth = sigmoid_meta.get('inflection_depth', np.nan)
                        shoulder_depth = sigmoid_meta.get('shoulder_depth', np.nan)
                    else:
                        inflection_depth = np.nan
                        shoulder_depth = np.nan
                except:
                    inflection_depth = np.nan
                    shoulder_depth = np.nan
            
            # Add sigmoid inflection
            if not np.isnan(inflection_depth):
                abs_y = int(surface_y + inflection_depth)
                if 0 <= abs_y < display_image.shape[0]:
                    method_raw_depths["sigmoid_fit"].append((x, abs_y))
            
            # Add sigmoid shoulder
            if not np.isnan(shoulder_depth):
                abs_y = int(surface_y + shoulder_depth)
                if 0 <= abs_y < display_image.shape[0]:
                    method_raw_depths["sigmoid_shoulder"].append((x, abs_y))
        
        # Get lesion region bounds for spline fitting
        if hasattr(lesion_depth, 'lesion_detection_data') and lesion_depth.lesion_detection_data:
            x_coords = list(lesion_depth.lesion_detection_data.keys())
            start_x = min(x_coords)
            end_x = max(x_coords)
        else:
            return
        
        # Draw each method
        for method_name, raw_points in method_raw_depths.items():
            if len(raw_points) < 4:  # Need at least 4 points for spline
                continue
            
            color = method_colors[method_name]
            
            # Compute smoothed spline for this method
            smoothed_curves = fit_surface_curve(
                raw_points,
                start_x,
                end_x,
                smoothing=0.5,
                smoothing_multiplier=1.0,
                spline_degree=3,
                curve_name=method_name
            )
            
            # Draw smoothed spline (always shown in comparison mode) - OPTIMIZED
            if method_name in smoothed_curves:
                smoothed_points = smoothed_curves[method_name]
                if len(smoothed_points) > 0:
                    # Vectorized drawing
                    points_array = np.array(smoothed_points, dtype=np.int32)
                    x_coords = points_array[:, 0]
                    y_coords = points_array[:, 1]
                    
                    valid_mask = (x_coords >= 0) & (x_coords < display_image.shape[1]) & \
                                (y_coords >= 0) & (y_coords < display_image.shape[0])
                    x_valid = x_coords[valid_mask]
                    y_valid = y_coords[valid_mask]
                    
                    # Draw with 3-pixel thickness
                    for dy in [-1, 0, 1]:
                        y_offset = y_valid + dy
                        offset_valid = (y_offset >= 0) & (y_offset < display_image.shape[0])
                        display_image[y_offset[offset_valid], x_valid[offset_valid]] = color
            
            # Draw raw points if toggle is enabled - OPTIMIZED
            if self.show_raw_depth.get() and len(raw_points) > 0:
                raw_array = np.array(raw_points, dtype=np.int32)
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        x_offset = raw_array[:, 0] + dx
                        y_offset = raw_array[:, 1] + dy
                        valid = (x_offset >= 0) & (x_offset < display_image.shape[1]) & \
                               (y_offset >= 0) & (y_offset < display_image.shape[0])
                        display_image[y_offset[valid], x_offset[valid]] = color
    
    def draw_method_comparison(self, draw, intensity_profile, depth_idx, surface_y, 
                              image_height, margin_left, margin_top, 
                              plot_area_width, plot_area_height):
        """Draw comparison of all detection methods on the A-Scan plot.
        
        OPTIMIZED: Uses pre-computed values from detection_metadata instead of recomputing.
        """
        # Get pre-computed detection metadata for current A-scan
        cache_key = (self.current_specimen.specimen_id, self.current_slice_index)
        if cache_key not in self.results_cache:
            return
        
        _, _, lesion_depth = self.results_cache[cache_key]
        if not lesion_depth or not lesion_depth.lesion_detection_data or self.current_ascan_x not in lesion_depth.lesion_detection_data:
            return
        
        detection_info = lesion_depth.lesion_detection_data[self.current_ascan_x]
        detection_metadata = detection_info.get('detection_metadata', {})
        
        # Define methods and their colors
        methods = [
            ("knee_point", "red", "Knee", 'knee_depth', 'knee_idx'),
            ("sigmoid_fit", "purple", "Inflection", 'inflection_depth', 'inflection_idx'),
            ("sigmoid_shoulder", "cyan", "Shoulder", 'shoulder_depth', 'shoulder_idx')
        ]
        
        results = {}
        
        # Use pre-computed values from metadata (FAST!)
        for method_name, color, label, depth_key, idx_key in methods:
            if depth_key in detection_metadata and idx_key in detection_metadata:
                depth_value = detection_metadata[depth_key]
                depth_index = detection_metadata[idx_key]
                
                if not np.isnan(depth_value) and depth_index >= 0 and depth_index < len(intensity_profile):
                    results[method_name] = (depth_value, depth_index, color, label)
        
        # Draw markers for each method
        marker_offset = 0
        for method_name, (depth_value, depth_index, color, label) in results.items():
            intensity = intensity_profile[depth_index]
            abs_y = surface_y + depth_value
            
            if abs_y < image_height:
                plot_x = margin_left + int((intensity / 255.0) * plot_area_width)
                plot_y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                
                # Draw marker (small square)
                size = 4
                draw.rectangle([(plot_x - size, plot_y - size), (plot_x + size, plot_y + size)], 
                             fill=color, outline='black', width=1)
                
                # Draw label to the right with offset
                draw.text((plot_x + 15, plot_y - 8 + marker_offset), 
                         f"{label}:{int(abs_y)}", fill=color)
                marker_offset += 12  # Stack labels vertically
    
    def update_ascan_plot(self):
        """Update the A-Scan intensity profile plot."""
        if self.current_image is None:
            return
        
        # Get canvas dimensions
        plot_width = self.plot_canvas.winfo_width()
        plot_height = self.plot_canvas.winfo_height()
        
        if plot_width <= 1 or plot_height <= 1:
            return
        
        # Extract A-Scan column (grayscale values)
        ascan_column = self.current_image[:, self.current_ascan_x]
        image_height = len(ascan_column)
        
        # Create plot image
        plot_img = Image.new('RGB', (plot_width, plot_height), 'white')
        draw = ImageDraw.Draw(plot_img)
        
        # Define plot margins
        margin_left = 50
        margin_right = 20
        margin_top = 20
        margin_bottom = 30
        
        plot_area_width = plot_width - margin_left - margin_right
        plot_area_height = plot_height - margin_top - margin_bottom
        
        if plot_area_width <= 0 or plot_area_height <= 0:
            return
        
        # Draw grid lines FIRST (behind data)
        grid_color = '#e0e0e0'  # Light gray for grid
        
        # Vertical grid lines (intensity axis) - every 32 intensity units (8 lines)
        for intensity in range(0, 256, 32):
            x = margin_left + int((intensity / 255.0) * plot_area_width)
            draw.line([(x, margin_top), (x, plot_height - margin_bottom)], fill=grid_color, width=1)
        
        # Horizontal grid lines (depth axis) - every 50 pixels (or adaptive based on image height)
        grid_spacing = max(50, image_height // 10)  # At least 10 grid lines
        for depth in range(0, image_height, grid_spacing):
            y = margin_top + int((depth / float(image_height - 1)) * plot_area_height)
            draw.line([(margin_left, y), (plot_width - margin_right, y)], fill=grid_color, width=1)
        
        # Draw axes (on top of grid)
        # Y-axis (depth)
        draw.line([(margin_left, margin_top), (margin_left, plot_height - margin_bottom)], fill='black', width=2)
        # X-axis (intensity)
        draw.line([(margin_left, plot_height - margin_bottom), (plot_width - margin_right, plot_height - margin_bottom)], fill='black', width=2)
        
        # X-axis labels and ticks (intensity: 0, 64, 128, 192, 255)
        for intensity in [0, 64, 128, 192, 255]:
            x = margin_left + int((intensity / 255.0) * plot_area_width)
            draw.line([(x, plot_height - margin_bottom), (x, plot_height - margin_bottom + 5)], fill='black', width=1)
            draw.text((x - 10, plot_height - margin_bottom + 8), str(intensity), fill='black')
        
        # Y-axis labels and ticks (depth: more granular)
        num_y_ticks = min(8, image_height // 50)  # 8 ticks or fewer
        for i in range(num_y_ticks + 1):
            depth = int((i / num_y_ticks) * (image_height - 1))
            y = margin_top + int((depth / float(image_height - 1)) * plot_area_height)
            draw.line([(margin_left - 5, y), (margin_left, y)], fill='black', width=1)
            draw.text((5, y - 5), str(depth), fill='black')
        
        # Plot the intensity profile
        points = []
        for y_idx, intensity in enumerate(ascan_column):
            x = margin_left + int((intensity / 255.0) * plot_area_width)
            y = margin_top + int((y_idx / float(image_height - 1)) * plot_area_height)
            points.append((x, y))
        
        # Draw the profile line
        if len(points) > 1:
            draw.line(points, fill='blue', width=2)
        
        # Mark detected surface point and fitted curve if available
        cache_key = (self.current_specimen.specimen_id, self.current_slice_index)
        if cache_key in self.results_cache:
            _, surface, lesion_depth = self.results_cache[cache_key]
            
            # Draw knee point detection visualization if available
            if lesion_depth and lesion_depth.lesion_detection_data and self.current_ascan_x in lesion_depth.lesion_detection_data:
                detection_info = lesion_depth.lesion_detection_data[self.current_ascan_x]
                intensity_profile = np.array(detection_info['intensity'])
                depth_idx = np.array(detection_info['depth_idx'])
                knee_idx = detection_info['knee_idx']
                surface_y = detection_info['surface_y']
                fitted_curve = detection_info.get('fitted_curve')
                
                # Draw the RAW intensity profile from surface downward (in green)
                profile_points = []
                for i, (d_idx, intensity) in enumerate(zip(depth_idx, intensity_profile)):
                    abs_y = surface_y + d_idx
                    if abs_y < image_height:
                        x = margin_left + int((intensity / 255.0) * plot_area_width)
                        y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                        profile_points.append((x, y))
                
                if len(profile_points) > 1:
                    draw.line(profile_points, fill='green', width=2)
                
                # Determine which fitted curve to show based on detection method
                detection_metadata = knee_info.get('detection_metadata', {})
                method_used = detection_metadata.get('method', 'knee_point')
                
                # COMPARISON MODE: Show all three methods with their fitted curves
                if self.compare_methods.get():
                    # Draw BOTH fitted curves (Exp2 and Sigmoid) if available
                    # Exp2 fit (magenta) - for knee_point method
                    # Use exp2_fitted_curve from metadata if available (compare mode)
                    exp2_curve = detection_metadata.get('exp2_fitted_curve')
                    if exp2_curve is not None:
                        exp2_curve_array = np.array(exp2_curve)
                        fitted_points = []
                        for i, (d_idx, intensity) in enumerate(zip(depth_idx, exp2_curve_array)):
                            abs_y = surface_y + d_idx
                            if abs_y < image_height:
                                x = margin_left + int((intensity / 255.0) * plot_area_width)
                                y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                                fitted_points.append((x, y))
                        
                        if len(fitted_points) > 1:
                            draw.line(fitted_points, fill='magenta', width=2)
                    elif fitted_curve is not None:
                        # Fallback to fitted_curve if exp2_fitted_curve not available
                        fitted_curve_array = np.array(fitted_curve)
                        fitted_points = []
                        for i, (d_idx, intensity) in enumerate(zip(depth_idx, fitted_curve_array)):
                            abs_y = surface_y + d_idx
                            if abs_y < image_height:
                                x = margin_left + int((intensity / 255.0) * plot_area_width)
                                y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                                fitted_points.append((x, y))
                        
                        if len(fitted_points) > 1:
                            draw.line(fitted_points, fill='magenta', width=2)
                    
                    # Sigmoid fit (purple) - for sigmoid methods
                    if 'sigmoid_fitted_curve' in detection_metadata:
                        sigmoid_curve = detection_metadata['sigmoid_fitted_curve']
                        if sigmoid_curve is not None:
                            sigmoid_curve = np.array(sigmoid_curve)
                            sigmoid_points = []
                            for i, (d_idx, intensity) in enumerate(zip(depth_idx, sigmoid_curve)):
                                abs_y = surface_y + d_idx
                                if abs_y < image_height:
                                    x = margin_left + int((intensity / 255.0) * plot_area_width)
                                    y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                                    sigmoid_points.append((x, y))
                            
                            if len(sigmoid_points) > 1:
                                draw.line(sigmoid_points, fill='purple', width=2)
                    
                    # Draw all three method markers
                    self.draw_method_comparison(draw, intensity_profile, depth_idx, surface_y, 
                                               image_height, margin_left, margin_top, 
                                               plot_area_width, plot_area_height)
                
                # SINGLE METHOD MODE: Show only the selected method
                else:
                    # Draw the FITTED curve (method-specific) if available
                    fit_color = 'magenta'
                    
                    if fitted_curve is not None:
                        fitted_curve = np.array(fitted_curve)
                        fitted_points = []
                        for i, (d_idx, intensity) in enumerate(zip(depth_idx, fitted_curve)):
                            abs_y = surface_y + d_idx
                            if abs_y < image_height:
                                x = margin_left + int((intensity / 255.0) * plot_area_width)
                                y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                                fitted_points.append((x, y))
                        
                        if len(fitted_points) > 1:
                            # Set color based on method
                            if method_used == 'knee_point':
                                fit_color = 'magenta'
                            elif method_used == 'sigmoid_fit':
                                fit_color = 'purple'
                            elif method_used == 'combined_mean':
                                fit_color = 'magenta'
                            
                            draw.line(fitted_points, fill=fit_color, width=3)
                    
                    # For combined method, also draw sigmoid fit
                    if method_used == 'combined_mean' and 'sigmoid_fitted_curve' in detection_metadata:
                        sigmoid_curve = detection_metadata['sigmoid_fitted_curve']
                        if sigmoid_curve is not None:
                            sigmoid_curve = np.array(sigmoid_curve)
                            sigmoid_points = []
                            for i, (d_idx, intensity) in enumerate(zip(depth_idx, sigmoid_curve)):
                                abs_y = surface_y + d_idx
                                if abs_y < image_height:
                                    x = margin_left + int((intensity / 255.0) * plot_area_width)
                                    y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                                    sigmoid_points.append((x, y))
                            
                            if len(sigmoid_points) > 1:
                                draw.line(sigmoid_points, fill='purple', width=3)
                    
                    # Draw primary method marker (large red circle)
                    if knee_idx >= 0 and knee_idx < len(intensity_profile):
                        knee_intensity = intensity_profile[knee_idx]
                        knee_abs_y = surface_y + depth_idx[knee_idx]
                        
                        if knee_abs_y < image_height:
                            plot_x = margin_left + int((knee_intensity / 255.0) * plot_area_width)
                            plot_y = margin_top + int((knee_abs_y / float(image_height - 1)) * plot_area_height)
                            
                            # Draw large marker for knee point
                            radius = 6
                            draw.ellipse([(plot_x - radius, plot_y - radius), 
                                        (plot_x + radius, plot_y + radius)], 
                                       fill='red', outline='darkred', width=3)
                            
                            # Add label (without font specification - use default)
                            method_labels = {
                                'knee_point': 'Knee',
                                'sigmoid_fit': 'Inflection',
                                'sigmoid_shoulder': 'Shoulder',
                                'combined_mean': 'Mean'
                            }
                            label_text = method_labels.get(method_used, 'Depth')
                            draw.text((plot_x + 10, plot_y - 10), f"{label_text}\ny={int(knee_abs_y)}", fill='red')
                            
                            # For combined method, draw individual markers
                            if method_used == 'combined_mean':
                                # Draw knee point marker (blue square)
                                if 'knee_depth' in detection_metadata and 'knee_idx' in detection_metadata:
                                    k_idx = detection_metadata['knee_idx']
                                    if 0 <= k_idx < len(intensity_profile):
                                        k_intensity = intensity_profile[k_idx]
                                        k_abs_y = surface_y + detection_metadata['knee_depth']
                                        k_plot_x = margin_left + int((k_intensity / 255.0) * plot_area_width)
                                        k_plot_y = margin_top + int((k_abs_y / float(image_height - 1)) * plot_area_height)
                                        
                                        size = 4
                                        draw.rectangle([(k_plot_x - size, k_plot_y - size), 
                                                      (k_plot_x + size, k_plot_y + size)], 
                                                     fill='blue', outline='darkblue', width=2)
                                        draw.text((k_plot_x - 40, k_plot_y - 5), f"K:{int(k_abs_y)}", fill='blue')
                                
                                # Draw sigmoid point marker (purple square)
                                if 'sigmoid_depth' in detection_metadata and 'sigmoid_idx' in detection_metadata:
                                    s_idx = detection_metadata['sigmoid_idx']
                                    if 0 <= s_idx < len(intensity_profile):
                                        s_intensity = intensity_profile[s_idx]
                                        s_abs_y = surface_y + detection_metadata['sigmoid_depth']
                                        s_plot_x = margin_left + int((s_intensity / 255.0) * plot_area_width)
                                        s_plot_y = margin_top + int((s_abs_y / float(image_height - 1)) * plot_area_height)
                                        
                                        size = 4
                                        draw.rectangle([(s_plot_x - size, s_plot_y - size), 
                                                      (s_plot_x + size, s_plot_y + size)], 
                                                     fill='purple', outline='darkviolet', width=2)
                                        draw.text((s_plot_x - 40, s_plot_y - 5), f"S:{int(s_abs_y)}", fill='purple')
                            
                            # For sigmoid-based methods, also show shoulder point
                            if method_used in ['sigmoid_fit', 'sigmoid_shoulder']:
                                # Draw shoulder point (cyan diamond)
                                if 'shoulder_depth' in detection_metadata and 'shoulder_idx' in detection_metadata:
                                    sh_idx = detection_metadata['shoulder_idx']
                                    if 0 <= sh_idx < len(intensity_profile):
                                        sh_intensity = intensity_profile[sh_idx]
                                        sh_abs_y = surface_y + detection_metadata['shoulder_depth']
                                        sh_plot_x = margin_left + int((sh_intensity / 255.0) * plot_area_width)
                                        sh_plot_y = margin_top + int((sh_abs_y / float(image_height - 1)) * plot_area_height)
                                        
                                        # Draw diamond shape for shoulder
                                        size = 5
                                        diamond_points = [
                                            (sh_plot_x, sh_plot_y - size),  # Top
                                            (sh_plot_x + size, sh_plot_y),  # Right
                                            (sh_plot_x, sh_plot_y + size),  # Bottom
                                            (sh_plot_x - size, sh_plot_y)   # Left
                                        ]
                                        draw.polygon(diamond_points, fill='cyan', outline='darkcyan')
                                        draw.text((sh_plot_x + 10, sh_plot_y - 20), f"Shoulder\ny={int(sh_abs_y)}", fill='cyan')
                                
                                # Draw inflection point (if not already the main marker)
                                if method_used != 'sigmoid_fit' and 'inflection_depth' in detection_metadata and 'inflection_idx' in detection_metadata:
                                    i_idx = detection_metadata['inflection_idx']
                                    if 0 <= i_idx < len(intensity_profile):
                                        i_intensity = intensity_profile[i_idx]
                                        i_abs_y = surface_y + detection_metadata['inflection_depth']
                                        i_plot_x = margin_left + int((i_intensity / 255.0) * plot_area_width)
                                        i_plot_y = margin_top + int((i_abs_y / float(image_height - 1)) * plot_area_height)
                                        
                                        # Draw small circle for inflection
                                        radius = 3
                                        draw.ellipse([(i_plot_x - radius, i_plot_y - radius), 
                                                    (i_plot_x + radius, i_plot_y + radius)], 
                                                   fill='purple', outline='darkviolet', width=1)
            
            # Draw actual surface point (orange) if enabled
            if self.show_fitted_curve.get() and surface and surface.fitted_curves and "actual_surface" in surface.fitted_curves:
                for x, y in surface.fitted_curves["actual_surface"]:
                    if x == self.current_ascan_x:
                        if 0 <= y < image_height:
                            spline_intensity = ascan_column[y]
                            plot_x = margin_left + int((spline_intensity / 255.0) * plot_area_width)
                            plot_y = margin_top + int((y / float(image_height - 1)) * plot_area_height)
                            
                            # Draw marker (orange circle for fitted curve)
                            radius = 4
                            draw.ellipse([(plot_x - radius, plot_y - radius), 
                                        (plot_x + radius, plot_y + radius)], 
                                       fill='orange', outline='darkorange', width=2)
                        break
            
            # Draw detected peak point (green) on top if enabled
            if self.show_surface.get() and surface and surface.raw_points:
                # Find surface point for current A-Scan
                for x, y in surface.raw_points:
                    if x == self.current_ascan_x:
                        # Get intensity at surface
                        if 0 <= y < image_height:
                            surface_intensity = ascan_column[y]
                            plot_x = margin_left + int((surface_intensity / 255.0) * plot_area_width)
                            plot_y = margin_top + int((y / float(image_height - 1)) * plot_area_height)
                            
                            # Draw marker (green circle for peak)
                            radius = 5
                            draw.ellipse([(plot_x - radius, plot_y - radius), 
                                        (plot_x + radius, plot_y + radius)], 
                                       fill='green', outline='darkgreen', width=2)
                            
                            # Add label
                            draw.text((plot_x + 8, plot_y - 8), f"Peak\ny={y}", fill='green')
                        break
        
        # Axis labels
        draw.text((plot_width // 2 - 30, plot_height - 10), "Intensity", fill='black')
        draw.text((5, 5), "Depth (px)", fill='black')
        
        # Add legend in lower right corner
        legend_x = plot_width - margin_right - 120
        legend_y = plot_height - margin_bottom - 40
        draw.text((legend_x, legend_y), "Blue: Full A-Scan", fill='blue')
        draw.text((legend_x, legend_y + 12), "Green: Lesion Profile", fill='green')
        
        # Add fit curve labels in top right
        if cache_key in self.results_cache:
            _, _, lesion_depth = self.results_cache[cache_key]
            if lesion_depth and lesion_depth.lesion_detection_data and self.current_ascan_x in lesion_depth.lesion_detection_data:
                detection_info = lesion_depth.lesion_detection_data[self.current_ascan_x]
                detection_meta = detection_info.get('detection_metadata', {})
                method_used = detection_meta.get('method', 'knee_point')
                fitted_curve = detection_info.get('fitted_curve')
                
                label_y = margin_top + 5
                
                # In comparison mode, always show both fits if available
                if self.compare_methods.get():
                    # Check for exp2_fitted_curve in metadata (compare mode) or fallback to fitted_curve
                    if detection_meta.get('exp2_fitted_curve') is not None or fitted_curve is not None:
                        draw.text((plot_width - margin_right - 100, label_y), 'Exp2 Fit', fill='magenta')
                    if 'sigmoid_fitted_curve' in detection_meta:
                        draw.text((plot_width - margin_right - 100, label_y + 15), 'Sigmoid Fit', fill='purple')
                
                # In single method mode, show only the relevant fit
                else:
                    if fitted_curve is not None:
                        if method_used == 'knee_point':
                            draw.text((plot_width - margin_right - 100, label_y), 'Exp2 Fit', fill='magenta')
                        elif method_used == 'sigmoid_fit':
                            draw.text((plot_width - margin_right - 100, label_y), 'Sigmoid Fit', fill='purple')
                        elif method_used == 'combined_mean':
                            draw.text((plot_width - margin_right - 100, label_y), 'Exp2 Fit', fill='magenta')
                            if 'sigmoid_fitted_curve' in detection_meta:
                                draw.text((plot_width - margin_right - 100, label_y + 15), 'Sigmoid Fit', fill='purple')
        
        # Convert to PhotoImage and display
        self.plot_photo = ImageTk.PhotoImage(plot_img)
        self.plot_canvas.delete("all")
        self.plot_canvas.create_image(0, 0, image=self.plot_photo, anchor=tk.NW)
    
    def clear_cache(self):
        """Clear the results cache."""
        self.results_cache.clear()
        self.update_display()
        self.update_info("Cache cleared")
    
    def update_info(self, text: str):
        """Update the info text panel."""
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, text)
    
    def update_slice_info(self):
        """Update info panel with current slice information."""
        if self.current_specimen is None:
            return
        
        info = f"Specimen: {self.current_specimen.specimen_id}\n"
        info += f"Slice: {self.current_slice_index + 1} / {len(self.current_specimen.images)}\n\n"
        
        # Check if we have results for this slice
        cache_key = (self.current_specimen.specimen_id, self.current_slice_index)
        if cache_key in self.results_cache:
            region_stats, surface, lesion_depth = self.results_cache[cache_key]
            
            # Surface information
            info += f"Surface peaks: {len(surface.raw_points)}\n"
            
            # Fitted curve information
            if surface.fitted_curves and "actual_surface" in surface.fitted_curves:
                info += f"Actual surface: {len(surface.fitted_curves['actual_surface'])} points\n"
            
            # Cavitation status
            if hasattr(surface, 'is_cavitated'):
                cavitation_status = "YES" if surface.is_cavitated else "NO"
                info += f"Cavitation detected: {cavitation_status}\n"
                if surface.is_cavitated:
                    info += f"Cavitation depth: {surface.cavitation_depth:.2f} pixels\n"
            
            # Cluster information
            if surface.cluster_labels:
                unique_clusters = np.unique(surface.cluster_labels)
                num_clusters = len(unique_clusters[unique_clusters >= 0])
                info += f"Surface clusters: {num_clusters}\n"
                for cluster_id in unique_clusters:
                    if cluster_id >= 0:
                        count = np.sum(np.array(surface.cluster_labels) == cluster_id)
                        info += f"  Cluster {cluster_id}: {count} peaks\n"
            
            # Lesion depth
            info += f"\nLesion depth: {lesion_depth.mean_depth:.2f} ± {lesion_depth.sd:.2f}\n"
            
            # Detection method used (if available in knee_data)
            if lesion_depth and lesion_depth.lesion_detection_data:
                first_x = next(iter(lesion_depth.lesion_detection_data))
                if 'detection_metadata' in lesion_depth.lesion_detection_data[first_x]:
                    method = lesion_depth.lesion_detection_data[first_x]['detection_metadata'].get('method', 'unknown')
                    info += f"Detection method: {method}\n"
                    
                    # For combined method, show method comparison info
                    if method == 'combined_mean':
                        detection_meta = lesion_depth.lesion_detection_data[first_x]['detection_metadata']
                        if 'knee_depth' in detection_meta and 'sigmoid_depth' in detection_meta:
                            # Calculate statistics across all A-Scans
                            differences = []
                            
                            for x, detection_info in lesion_depth.lesion_detection_data.items():
                                meta = detection_info.get('detection_metadata', {})
                                if 'knee_depth' in meta and 'sigmoid_depth' in meta:
                                    k_depth = meta['knee_depth']
                                    s_depth = meta['sigmoid_depth']
                                    diff = abs(k_depth - s_depth)
                                    differences.append(diff)
                            
                            if differences:
                                avg_diff = np.mean(differences)
                                min_diff = np.min(differences)
                                max_diff = np.max(differences)
                                
                                info += f"  Method disagreement:\n"
                                info += f"    Average: {avg_diff:.2f} px\n"
                                info += f"    Range: {min_diff:.2f} - {max_diff:.2f} px\n"
            if lesion_depth.depth_points:
                info += f"  Raw depth points: {len(lesion_depth.depth_points)}\n"
            if lesion_depth.smoothed_depth_points:
                info += f"  Smoothed depth points: {len(lesion_depth.smoothed_depth_points)}\n"
            info += "\n"
            
            # Method Stability Analysis (if available)
            if hasattr(lesion_depth, 'method_splines') and lesion_depth.method_splines:
                if 'stability_info' in lesion_depth.method_splines:
                    stability_info = lesion_depth.method_splines['stability_info']
                    
                    info += "═══ Method Stability Analysis ═══\n"
                    info += "(SD = Standard Deviation in pixels)\n\n"
                    
                    # Define method display names
                    method_names = {
                        'knee_point': 'Knee Point (Exp2)',
                        'sigmoid_fit': 'Sigmoid Inflection',
                        'sigmoid_shoulder': 'Sigmoid Shoulder'
                    }
                    
                    # Sort methods by SD (most stable/lowest SD first)
                    sorted_methods = sorted(
                        stability_info.items(),
                        key=lambda x: x[1].get('cv', float('inf'))  # 'cv' field now contains SD
                    )
                    
                    for method_key, stats in sorted_methods:
                        if method_key in method_names:
                            display_name = method_names[method_key]
                            cv = stats.get('cv', float('inf'))
                            is_stable = stats.get('is_stable', False)
                            n_points = stats.get('n_points', 0)
                            mean_depth = stats.get('mean_depth', 0)
                            std_depth = stats.get('std_depth', 0)
                            
                            # Status indicator
                            status = "✓ STABLE" if is_stable else "✗ UNSTABLE"
                            status_color = "✓" if is_stable else "✗"
                            
                            info += f"{status_color} {display_name}:\n"
                            info += f"    SD: {cv:.1f}px - {status}\n"
                            info += f"    Mean: {mean_depth:.1f}px\n"
                            info += f"    Points: {n_points}\n"
                            info += "\n"
                    
                    # Show which methods were used for combined mean
                    if lesion_depth.lesion_detection_data:
                        first_x = next(iter(lesion_depth.lesion_detection_data))
                        detection_meta = lesion_depth.lesion_detection_data[first_x].get('detection_metadata', {})
                        if 'combined_method_used' in detection_meta:
                            methods_used = detection_meta['combined_method_used']
                            info += f"Combined Mean Uses:\n"
                            if methods_used.startswith('fallback_'):
                                fallback_method = methods_used.replace('fallback_', '')
                                info += f"  ⚠ Fallback: {method_names.get(fallback_method, fallback_method)}\n"
                                info += f"  (No methods were stable)\n"
                            else:
                                used_methods = methods_used.split('+')
                                for m in used_methods:
                                    info += f"  • {method_names.get(m, m)}\n"
        else:
            info += "No analysis results for this slice.\n"
            info += "Click 'Run Algorithm' to analyze.\n"
        
        self.update_info(info)


def main():
    """Main entry point for the test viewer."""
    root = tk.Tk()
    app = CarlQuantTestViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
