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
from PIL import Image, ImageTk
import numpy as np
from pathlib import Path
from typing import Optional, Dict
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
        
        # Display state
        self.show_surface = tk.BooleanVar(value=True)
        self.show_regions = tk.BooleanVar(value=True)
        self.show_air = tk.BooleanVar(value=True)
        self.show_lesion_depth = tk.BooleanVar(value=True)
        
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
        
        # Right panel: Image display
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
        
        ttk.Label(algo_frame, text="Sound Regions:").pack(anchor=tk.W)
        self.sound_regions_var = tk.IntVar(value=3)
        sound_spin = ttk.Spinbox(algo_frame, from_=1, to=10, textvariable=self.sound_regions_var, width=10)
        sound_spin.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(algo_frame, text="Lesion Regions:").pack(anchor=tk.W)
        self.lesion_regions_var = tk.IntVar(value=3)
        lesion_spin = ttk.Spinbox(algo_frame, from_=1, to=10, textvariable=self.lesion_regions_var, width=10)
        lesion_spin.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(algo_frame, text="Run Algorithm", command=self.run_algorithm).pack(fill=tk.X, pady=(5, 0))
        ttk.Button(algo_frame, text="Clear Cache", command=self.clear_cache).pack(fill=tk.X, pady=(5, 0))
        
        # Display options
        display_frame = ttk.LabelFrame(parent, text="Display Options", padding=10)
        display_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(display_frame, text="Show Surface", variable=self.show_surface,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Regions", variable=self.show_regions,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show AIR", variable=self.show_air,
                       command=self.update_display).pack(anchor=tk.W)
        ttk.Checkbutton(display_frame, text="Show Lesion Depth", variable=self.show_lesion_depth,
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
        """Setup the image display panel."""
        # Canvas for image display
        self.canvas = tk.Canvas(parent, bg='#2b2b2b', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
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
        
        # Update label
        self.slice_label.config(text=f"Slice: {slice_idx + 1} / {len(self.current_specimen.images)}")
        
        # Display with overlays
        self.update_display()
    
    def update_display(self):
        """Update the canvas display with current image and overlays."""
        if self.current_image is None:
            return
        
        # Start with grayscale image
        display_image = self.current_image.copy()
        
        # Convert to RGB for overlays
        if len(display_image.shape) == 2:
            display_image = np.stack([display_image] * 3, axis=-1)
        
        # Check if we have results for this slice
        cache_key = (self.current_specimen.specimen_id, self.current_slice_index)
        if cache_key in self.results_cache:
            region_stats, surface, lesion_depth = self.results_cache[cache_key]
            
            # Draw surface
            if self.show_surface.get() and surface:
                for x, y in surface.raw_points:
                    if 0 <= x < display_image.shape[1] and 0 <= y < display_image.shape[0]:
                        # Draw a small cross
                        for dx in range(-2, 3):
                            for dy in range(-2, 3):
                                nx, ny = x + dx, y + dy
                                if 0 <= nx < display_image.shape[1] and 0 <= ny < display_image.shape[0]:
                                    if abs(dx) <= 1 or abs(dy) <= 1:
                                        display_image[ny, nx] = [255, 0, 0]  # Red
        
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
    
    def run_algorithm(self):
        """Run the CarlQuant algorithm on current slice."""
        if self.current_specimen is None or self.current_specimen.config is None:
            messagebox.showwarning("No Configuration", "Please select a specimen with configuration.")
            return
        
        if self.current_slice_index not in self.current_specimen.config.regions:
            messagebox.showwarning("No Region Config", f"No region configuration for slice {self.current_slice_index + 1}")
            return
        
        self.update_info("Reloading algorithm module...")
        self.status_label.config(text="Reloading...")
        self.root.update()
        
        try:
            # Hot-reload the algorithm module to pick up changes
            importlib.reload(test_carlquant_algorithm)
            self.update_info("Running algorithm...")
            self.status_label.config(text="Processing...")
            self.root.update()
            
            # Get configuration
            region_config = self.current_specimen.config.regions[self.current_slice_index]
            air_config = self.current_specimen.config.air.get(self.current_slice_index)
            
            # Run algorithm (use reloaded module)
            image_path = self.current_specimen.images[self.current_slice_index]
            region_stats, surface, lesion_depth = test_carlquant_algorithm.process_slice(
                image_path,
                region_config,
                air_config,
                self.sound_regions_var.get(),
                self.lesion_regions_var.get()
            )
            
            # Cache results
            cache_key = (self.current_specimen.specimen_id, self.current_slice_index)
            self.results_cache[cache_key] = (region_stats, surface, lesion_depth)
            
            # Update display
            self.update_display()
            
            # Update info
            info = f"Algorithm Results (Slice {self.current_slice_index + 1}):\n"
            info += f"Surface points: {len(surface.raw_points)}\n"
            info += f"Lesion depth: {lesion_depth.mean_depth:.2f} ± {lesion_depth.sd:.2f}\n\n"
            info += "Region Statistics:\n"
            for i, stats in enumerate(region_stats):
                info += f"  {stats.region_type.upper()} {i+1}: "
                info += f"median={stats.median:.2f}, sd={stats.sd:.2f}\n"
            
            self.update_info(info)
            self.status_label.config(text="Algorithm completed")
            
        except Exception as e:
            messagebox.showerror("Algorithm Error", f"Error running algorithm:\n{str(e)}")
            self.status_label.config(text="Error")
            import traceback
            traceback.print_exc()
    
    def clear_cache(self):
        """Clear the results cache."""
        self.results_cache.clear()
        self.update_display()
        self.update_info("Cache cleared")
    
    def update_info(self, text: str):
        """Update the info text panel."""
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, text)


def main():
    """Main entry point for the test viewer."""
    root = tk.Tk()
    app = CarlQuantTestViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
