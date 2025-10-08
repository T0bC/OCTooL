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

# Add parent directory to path so we can import from carlquant_frames
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_carlquant_config import load_test_specimens, load_single_specimen, TestConfig
import test_carlquant_algorithm
from carlquant_frames.specimen_model import Specimen


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
        self.show_ascan = tk.BooleanVar(value=True)
        
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
        ttk.Checkbutton(display_frame, text="Show Lesion Depth", variable=self.show_lesion_depth,
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
            
            # Draw reference curve first (cyan) - bottom layer
            if self.show_reference_curve.get() and surface:
                if surface.fitted_curves and "reference" in surface.fitted_curves:
                    for x, y in surface.fitted_curves["reference"]:
                        if 0 <= x < display_image.shape[1] and 0 <= y < display_image.shape[0]:
                            # Draw thicker line (3 pixels vertical thickness)
                            for dy in range(-1, 2):
                                ny = y + dy
                                if 0 <= ny < display_image.shape[0]:
                                    display_image[ny, x] = [0, 255, 255]  # Cyan
            
            # Draw fitted spline curve (orange) with thickness - middle layer
            if self.show_fitted_curve.get() and surface:
                if surface.fitted_curves and "spline" in surface.fitted_curves:
                    for x, y in surface.fitted_curves["spline"]:
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
        
        # Draw lesion depth
        if self.show_lesion_depth.get() and cache_key in self.results_cache:
            _, _, lesion_depth = self.results_cache[cache_key]
            if lesion_depth:
                for x, depth in lesion_depth.depth_points:
                    if 0 <= x < display_image.shape[1]:
                        # Draw depth marker
                        for dy in range(-1, 2):
                            y = int(depth) + dy
                            if 0 <= y < display_image.shape[0]:
                                display_image[y, x] = [0, 255, 0]  # Green
        
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
        """Run the CarlQuant algorithm on all slices."""
        if self.current_specimen is None or self.current_specimen.config is None:
            messagebox.showwarning("No Configuration", "Please select a specimen with configuration.")
            return
        
        self.update_info("Reloading algorithm module...")
        self.status_label.config(text="Reloading...")
        self.root.update()
        
        try:
            # Hot-reload the algorithm module to pick up changes
            importlib.reload(test_carlquant_algorithm)
            
            # Process all slices
            num_slices = len(self.current_specimen.images)
            processed_count = 0
            
            for slice_idx in range(num_slices):
                # Check if this slice has configuration
                if slice_idx not in self.current_specimen.config.regions:
                    continue
                
                # Update UI less frequently (every 5 slices)
                if slice_idx % 5 == 0 or slice_idx == num_slices - 1:
                    self.status_label.config(text=f"Processing {slice_idx + 1}/{num_slices}...")
                    self.root.update_idletasks()  # Use update_idletasks instead of update
                
                # Get configuration
                region_config = self.current_specimen.config.regions[slice_idx]
                air_config = self.current_specimen.config.air.get(slice_idx)
                
                # Run algorithm (use reloaded module)
                image_path = self.current_specimen.images[slice_idx]
                num_regions = self.num_regions_var.get()
                # Sound regions: half of total (split between left and right)
                # Lesion regions: all of total
                num_sound = num_regions // 2
                num_lesion = num_regions
                
                region_stats, surface, lesion_depth = test_carlquant_algorithm.process_slice(
                    image_path,
                    region_config,
                    air_config,
                    num_sound,
                    num_lesion
                )
                
                # Cache results
                cache_key = (self.current_specimen.specimen_id, slice_idx)
                self.results_cache[cache_key] = (region_stats, surface, lesion_depth)
                processed_count += 1
            
            # Update status and display
            self.status_label.config(text=f"Completed: {processed_count} slices processed")
            
            # Update display (which will automatically update info panel)
            self.update_display()
            
        except Exception as e:
            messagebox.showerror("Algorithm Error", f"Error running algorithm:\n{str(e)}")
            self.status_label.config(text="Error")
            import traceback
            traceback.print_exc()
    
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
        
        # Draw axes
        # Y-axis (depth)
        draw.line([(margin_left, margin_top), (margin_left, plot_height - margin_bottom)], fill='black', width=2)
        # X-axis (intensity)
        draw.line([(margin_left, plot_height - margin_bottom), (plot_width - margin_right, plot_height - margin_bottom)], fill='black', width=2)
        
        # Draw grid and labels
        # X-axis labels (intensity: 0, 128, 255)
        for intensity in [0, 128, 255]:
            x = margin_left + int((intensity / 255.0) * plot_area_width)
            draw.line([(x, plot_height - margin_bottom), (x, plot_height - margin_bottom + 5)], fill='black', width=1)
            draw.text((x - 10, plot_height - margin_bottom + 8), str(intensity), fill='black')
        
        # Y-axis labels (depth: 0, middle, max)
        for depth_idx, depth in enumerate([0, image_height // 2, image_height - 1]):
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
            if lesion_depth and lesion_depth.knee_data and self.current_ascan_x in lesion_depth.knee_data:
                knee_info = lesion_depth.knee_data[self.current_ascan_x]
                intensity_profile = np.array(knee_info['intensity'])
                depth_idx = np.array(knee_info['depth_idx'])
                knee_idx = knee_info['knee_idx']
                surface_y = knee_info['surface_y']
                fitted_curve = knee_info.get('fitted_curve')
                
                # Draw the RAW intensity profile from surface downward (in light gray/thin)
                profile_points = []
                for i, (d_idx, intensity) in enumerate(zip(depth_idx, intensity_profile)):
                    abs_y = surface_y + d_idx
                    if abs_y < image_height:
                        x = margin_left + int((intensity / 255.0) * plot_area_width)
                        y = margin_top + int((abs_y / float(image_height - 1)) * plot_area_height)
                        profile_points.append((x, y))
                
                if len(profile_points) > 1:
                    draw.line(profile_points, fill='lightgray', width=1)
                
                # Draw the FITTED exp2 curve (in magenta/thick) if available
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
                        draw.line(fitted_points, fill='magenta', width=3)
                
                # Draw knee point marker (large red circle)
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
                        draw.text((plot_x + 10, plot_y - 10), f"Knee\ny={int(knee_abs_y)}", fill='red')
            
            # Draw fitted spline point (orange) if enabled
            if self.show_fitted_curve.get() and surface and surface.fitted_curves and "spline" in surface.fitted_curves:
                for x, y in surface.fitted_curves["spline"]:
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
            if surface.fitted_curves and "spline" in surface.fitted_curves:
                info += f"Fitted curve: {len(surface.fitted_curves['spline'])} points (spline)\n"
            
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
            info += f"\nLesion depth: {lesion_depth.mean_depth:.2f} ± {lesion_depth.sd:.2f}\n\n"
            
            # Region statistics
            info += "Region Statistics:\n"
            for i, stats in enumerate(region_stats):
                info += f"  {stats.region_type.upper()} {i+1}: "
                info += f"median={stats.median:.2f}, sd={stats.sd:.2f}\n"
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
