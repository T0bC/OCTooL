# -*- coding: utf-8 -*-
"""
Base Canvas Panel for OCTexVIEW Application

This module provides a base class for canvas-based image viewers with common
functionality including zoom, pan, navigation, and coordinate conversion.

Specialized panels (annotation, region selection, etc.) should inherit from
this class and override the hook methods to implement custom behavior.

Created on Thu Oct 02 09:43:00 2025
@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors
from utils.instruction_renderer import InstructionRenderer


class BaseCanvasPanel:
    """
    Abstract base class for canvas-based image viewers.
    
    This class centralizes common functionality used across analyze_frames and
    carlquant_frames panels, eliminating ~400-500 lines of duplicate code.
    
    Common Functionality Provided:
    - Image display with zoom (Ctrl+MouseWheel, 1.0x to 10.0x)
    - Pan when zoomed (Ctrl+Drag)
    - Navigation (arrow keys, mouse wheel, slider)
    - Coordinate conversion (canvas ↔ image)
    - Canvas resize handling with aspect ratio preservation
    - Instruction text rendering via InstructionRenderer
    - Automatic focus management for reliable keyboard/mouse input in tabbed interfaces
    
    Hook Methods (override in subclasses for specialized behavior):
    - setup_specialized_bindings(): Add custom mouse/keyboard bindings
    - draw_specialized_overlays(): Draw annotations, regions, etc. after image render
    - get_instruction_key(): Return instruction key for InstructionRenderer
    - get_image_list(): Return list of images to display
    - get_image_path(index): Return path to specific image
    
    Usage Example:
        class MyPanel(BaseCanvasPanel):
            def __init__(self, context):
                super().__init__(context, "my_frame_key")
            
            def setup_specialized_bindings(self):
                self.canvas.bind("<ButtonPress-1>", self.on_click)
            
            def draw_specialized_overlays(self):
                # Draw custom overlays here
                pass
            
            def get_instruction_key(self):
                return 'my_instructions'
            
            def get_image_list(self):
                return self.context.my_image_list
    """
    
    @handle_errors("error in BaseCanvasPanel.__init__")
    def __init__(self, context, frame_key, canvas_bg='#505050'):
        """
        Initialize the base canvas panel.
        
        IMPORTANT: Subclasses should initialize any state needed by hook methods
        BEFORE calling super().__init__(), since setup_specialized_bindings() is
        called at the end of this __init__ method.
        
        Args:
            context: Application context providing access to shared state
            frame_key: Key to retrieve the frame from context (e.g., "image", "carl_image")
            canvas_bg: Background color for the canvas (default: '#505050')
        """
        self.context = context
        self.root = context.root
        self.frame = context.get_frame(frame_key)
        self.window = self.frame.winfo_toplevel()
        
        # Zoom and pan state
        self.zoom_level = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        
        # Image state
        self.rawImage = None
        self.tk_image = None
        self.fitted_width = None
        self.fitted_height = None
        
        # Overlay visibility state
        self.overlays_visible = True
        
        # Configure frame grid
        self.frame.rowconfigure(1, weight=1)
        self.frame.rowconfigure(3, weight=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=0)
        
        # Create canvas
        self.canvas = tk.Canvas(self.frame, width=1024, height=480, 
                               highlightthickness=0, bg=canvas_bg)
        self.canvas.grid(row=1, column=0, columnspan=3, sticky="nsew")
        
        # Make canvas focusable for keyboard events
        self.canvas.config(takefocus=True)
        
        # Setup common bindings
        self._setup_common_bindings()
        
        # Initialize instruction renderer
        self.instruction_renderer = InstructionRenderer(self.canvas)
        self.instruction_renderer.set_logo("icons/WBM_UL_RGB_digital_Path.png")
        
        # Create slider
        self.scaleValue = tk.StringVar()
        self.scale = ttk.Scale(self.frame, from_=1, to=1,
                              orient='horizontal',
                              bootstyle="warning")
        self.scale.set(1)
        self.scale.grid(row=3, column=0, columnspan=2, sticky="ew")
        
        self.scaleValueLabel = ttk.Label(self.frame, text="text", 
                                        textvariable=self.scaleValue)
        self.scaleValueLabel.grid(row=3, column=2, sticky=tk.E)
        Tooltip(self.scale, text='Move the slider to display a different slice.', 
               wraplength=200)
        
        self.setup_scale_callback()
        
        # Allow subclasses to add specialized bindings
        self.setup_specialized_bindings()
        
        # Show initial instructions
        self.root.after(100, self.instructionText)
    
    def _setup_common_bindings(self):
        """Setup common keyboard and mouse bindings for navigation and zoom."""
        # Navigation bindings (window-level for keyboard shortcuts)
        self.window.bind("<Left>", self.on_arrow_left)
        self.window.bind("<Right>", self.on_arrow_right)
        self.window.bind("<MouseWheel>", self.on_mouse_wheel)
        self.window.bind("<Button-4>", self.on_mouse_wheel_linux)
        self.window.bind("<Button-5>", self.on_mouse_wheel_linux)
        
        # Canvas bindings
        self.canvas.bind("<Configure>", self.onResize)
        
        # Keyboard navigation on canvas (for better reliability in tabbed interfaces)
        self.canvas.bind("<Left>", self.on_arrow_left)
        self.canvas.bind("<Right>", self.on_arrow_right)
        
        # Mouse wheel bindings on canvas (for better reliability in tabbed interfaces)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel_linux)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel_linux)
        
        # Zoom bindings
        self.canvas.bind("<Control-MouseWheel>", self.on_mouse_wheel_zoom)
        self.canvas.bind("<Control-Button-4>", self.on_mouse_wheel_zoom)
        self.canvas.bind("<Control-Button-5>", self.on_mouse_wheel_zoom)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        
        # Pan bindings
        self.canvas.bind("<Control-ButtonPress-1>", self.start_pan)
        self.canvas.bind("<Control-B1-Motion>", self.do_pan)
        self.canvas.bind("<Control-ButtonRelease-1>", self.end_pan)
        
        # Focus management: give canvas focus when mouse enters or clicks
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<Button-1>", self._ensure_focus, add=True)
    
    def _ensure_focus(self, event):
        """
        Ensure canvas has focus when clicked.
        Uses add=True in binding to not interfere with other click handlers.
        """
        self.canvas.focus_set()
    
    # ============================================================================
    # HOOK METHODS - Override these in subclasses for specialized behavior
    # ============================================================================
    
    def setup_specialized_bindings(self):
        """
        Hook method: Setup specialized mouse/keyboard bindings.
        Override this in subclasses to add custom event handlers.
        """
        pass
    
    def draw_specialized_overlays(self):
        """
        Hook method: Draw specialized overlays on the image.
        Override this in subclasses to draw annotations, regions, etc.
        Called after image rendering.
        
        Note: Subclasses should check self.overlays_visible before drawing
        overlays to respect the toggle state.
        """
        pass
    
    def get_instruction_key(self):
        """
        Hook method: Return the instruction key for this panel.
        Override this in subclasses to specify which instructions to display.
        
        Returns:
            str: Key for instructions.json (e.g., 'analyze_getting_started')
        """
        return None
    
    def get_image_list(self):
        """
        Hook method: Return the list of images to display.
        Override this in subclasses to specify the image source.
        
        Returns:
            list: List of image paths or image data dictionaries
        """
        return []
    
    def get_image_path(self, index):
        """
        Hook method: Return the path to the image at the given index.
        Override this in subclasses to specify how to get image paths.
        
        Args:
            index: 0-based image index
            
        Returns:
            str: Path to the image file
        """
        image_list = self.get_image_list()
        if 0 <= index < len(image_list):
            # Handle both dict format {'path': ...} and direct path strings
            if isinstance(image_list[index], dict):
                return image_list[index].get('path')
            return image_list[index]
        return None
    
    # ============================================================================
    # COORDINATE CONVERSION
    # ============================================================================
    
    @handle_errors("BaseCanvasPanel.canvas_to_image_coords")
    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """
        Convert canvas coordinates to image coordinates.
        
        Takes into account current zoom level and pan offset.
        
        Args:
            canvas_x: X coordinate on canvas
            canvas_y: Y coordinate on canvas
        
        Returns:
            tuple: (image_x, image_y) or (None, None) if no image loaded
        """
        if not hasattr(self, 'rawImage') or self.rawImage is None:
            return None, None
        
        # Use fitted size if zoom_level == 1.0
        if self.zoom_level == 1.0:
            current_zoom = self.fitted_width / self.rawImage.width if self.fitted_width else 1.0
        else:
            current_zoom = self.zoom_level
        
        img_x = (canvas_x - self.image_offset_x) / current_zoom
        img_y = (canvas_y - self.image_offset_y) / current_zoom
        
        return img_x, img_y
    
    @handle_errors("BaseCanvasPanel.image_to_canvas_coords")
    def image_to_canvas_coords(self, img_x, img_y):
        """
        Convert image coordinates to canvas coordinates.
        
        Takes into account current zoom level and pan offset.
        
        Args:
            img_x: X coordinate in image space
            img_y: Y coordinate in image space
        
        Returns:
            tuple: (canvas_x, canvas_y)
        """
        if not hasattr(self, 'rawImage') or self.rawImage is None:
            return img_x, img_y
        
        # Use fitted size if zoom_level == 1.0
        if self.zoom_level == 1.0:
            current_zoom = self.fitted_width / self.rawImage.width if self.fitted_width else 1.0
        else:
            current_zoom = self.zoom_level
        
        x = img_x * current_zoom + self.image_offset_x
        y = img_y * current_zoom + self.image_offset_y
        
        return x, y
    
    # ============================================================================
    # IMAGE RENDERING
    # ============================================================================
    
    @handle_errors("BaseCanvasPanel.render_zoomed_image")
    def render_zoomed_image(self):
        """
        Render the current image with applied zoom and pan transformations.
        
        At zoom_level=1.0, the image is fitted to the canvas while preserving
        aspect ratio. At higher zoom levels, the image is scaled accordingly.
        After rendering, specialized overlays are drawn via hook method.
        """
        if self.rawImage is None:
            return
        
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
        zoomed = self.rawImage.resize((zoomed_width, zoomed_height), 
                                     Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(zoomed)
        
        # Draw image
        self.canvas.delete("all")
        self.canvas.create_image(self.image_offset_x, self.image_offset_y, 
                                image=self.tk_image, anchor=tk.NW)
        self.canvas.update_idletasks()
        
        # Call hook for specialized overlays
        self.draw_specialized_overlays()
    
    @handle_errors("BaseCanvasPanel.display_image")
    def display_image(self, index=None):
        """
        Display an image from the image list.
        
        Args:
            index: 0-based slice index. If None, uses current slider position.
        """
        self.canvas.delete("all")
        
        image_list = self.get_image_list()
        self.scale.configure(from_=1, to=len(image_list))
        
        if not image_list:
            return
        
        if index is None:
            index = int(self.scale.get() - 1)
        
        if index < 0 or index >= len(image_list):
            return
        
        try:
            img_path = self.get_image_path(index)
            if img_path is None:
                return
            
            img = Image.open(img_path)
            self.rawImage = img.copy()
            
            # Reset zoom and pan
            self.zoom_level = 1.0
            self.image_offset_x = 0
            self.image_offset_y = 0
            
            self.render_zoomed_image()
            self.scaleValue.set(f"Slice {index + 1} / {len(image_list)}")
            
            # Give canvas focus so keyboard shortcuts work immediately
            self.canvas.focus_set()
            
        except Exception as e:
            # Try to update status bar if available
            if hasattr(self.context, 'status_bar') and self.context.status_bar:
                self.context.status_bar.update(f"Error displaying image: {e}", 
                                              level="error")
            else:
                print(f"Error displaying image: {e}")
    
    @handle_errors("BaseCanvasPanel.instructionText")
    def instructionText(self):
        """
        Display instruction text and logo when no image is loaded.
        Uses the instruction key from get_instruction_key() hook method.
        """
        instruction_key = self.get_instruction_key()
        if instruction_key:
            self.instruction_renderer.render(instruction_key)
    
    # ============================================================================
    # ZOOM AND PAN
    # ============================================================================
    
    @handle_errors("BaseCanvasPanel.on_mouse_wheel_zoom")
    def on_mouse_wheel_zoom(self, event):
        """
        Handle zoom via Ctrl+MouseWheel.
        
        Zooms in/out while keeping the content under the mouse cursor fixed.
        Zoom range: 1.0 (fit to canvas) to 10.0 (10x magnification).
        
        Args:
            event: Mouse wheel event with delta and position information
        """
        if not hasattr(self, 'rawImage') or self.rawImage is None:
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
        if event.delta > 0 or getattr(event, 'num', None) == 4:
            self.zoom_level = min(self.zoom_level + 0.25, 10.0)
        elif event.delta < 0 or getattr(event, 'num', None) == 5:
            self.zoom_level = max(self.zoom_level - 0.25, 1.0)
        
        # Compute new offset to keep content under cursor fixed
        self.image_offset_x = mouse_x - rel_x * self.zoom_level
        self.image_offset_y = mouse_y - rel_y * self.zoom_level
        
        self.render_zoomed_image()
    
    @handle_errors("BaseCanvasPanel.start_pan")
    def start_pan(self, event):
        """
        Start panning operation (Ctrl+LeftClick).
        
        Args:
            event: Mouse button press event
        """
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.canvas.config(cursor="fleur")
    
    @handle_errors("BaseCanvasPanel.do_pan")
    def do_pan(self, event):
        """
        Perform panning while Ctrl+Drag is active.
        
        Updates image offset and clamps to prevent dragging image completely
        out of view.
        
        Args:
            event: Mouse motion event
        """
        if not self.is_panning or self.rawImage is None:
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
    
    @handle_errors("BaseCanvasPanel.end_pan")
    def end_pan(self, event):
        """
        End panning operation (Ctrl+LeftRelease).
        
        Args:
            event: Mouse button release event
        """
        self.is_panning = False
        self.canvas.config(cursor="arrow")
    
    # ============================================================================
    # NAVIGATION
    # ============================================================================
    
    @handle_errors("BaseCanvasPanel.on_arrow_left")
    def on_arrow_left(self, event):
        """
        Navigate to previous slice (Left arrow key or scroll up).
        
        Args:
            event: Keyboard or mouse wheel event
        """
        current = int(self.scale.get())
        if current > 1:
            self.scale.set(current - 1)
            self.display_image(current - 2)
    
    @handle_errors("BaseCanvasPanel.on_arrow_right")
    def on_arrow_right(self, event):
        """
        Navigate to next slice (Right arrow key or scroll down).
        
        Args:
            event: Keyboard or mouse wheel event
        """
        current = int(self.scale.get())
        if current < int(self.scale.cget("to")):
            self.scale.set(current + 1)
            self.display_image(current)
    
    @handle_errors("BaseCanvasPanel.on_mouse_wheel")
    def on_mouse_wheel(self, event):
        """
        Handle mouse wheel scroll for Windows/macOS.
        
        Without Ctrl: Navigate between slices
        With Ctrl: Zoom (handled by on_mouse_wheel_zoom)
        
        Args:
            event: Mouse wheel event
        """
        if event.state & 0x0004:  # Ctrl is pressed
            return  # Let canvas handle zoom
        if event.delta > 0:
            self.on_arrow_left(event)
        else:
            self.on_arrow_right(event)
    
    @handle_errors("BaseCanvasPanel.on_mouse_wheel_linux")
    def on_mouse_wheel_linux(self, event):
        """
        Handle mouse wheel scroll for Linux.
        
        Without Ctrl: Navigate between slices
        With Ctrl: Zoom (handled by on_mouse_wheel_zoom)
        
        Args:
            event: Mouse wheel event (Button-4 = up, Button-5 = down)
        """
        if event.state & 0x0004:  # Ctrl is pressed
            return  # Let canvas handle zoom
        if event.num == 4:
            self.on_arrow_left(event)
        elif event.num == 5:
            self.on_arrow_right(event)
    
    @handle_errors("BaseCanvasPanel.setup_scale_callback")
    def setup_scale_callback(self):
        """Configure the slider callback for slice navigation."""
        self.scale.configure(command=self.on_scale_change)
    
    @handle_errors("BaseCanvasPanel.on_scale_change")
    def on_scale_change(self, value):
        """
        Handle slider value changes.
        
        Args:
            value: New slider value (1-based slice number)
        """
        index = int(round(float(value))) - 1
        self.display_image(index)
    
    # ============================================================================
    # UI EVENT HANDLERS
    # ============================================================================
    
    @handle_errors("BaseCanvasPanel.onResize")
    def onResize(self, event):
        """
        Handle canvas resize events.
        
        Refreshes the displayed image to fit the new canvas dimensions.
        
        Args:
            event: Canvas configure event with new width/height
        """
        self.width = event.width
        self.height = event.height
        
        if hasattr(self, 'tk_image') and self.tk_image is not None:
            self.display_image(int(self.scale.get()) - 1)
        else:
            self.instructionText()
    
    # ============================================================================
    # OVERLAY VISIBILITY TOGGLE
    # ============================================================================
    
    @handle_errors("BaseCanvasPanel.toggle_overlays")
    def toggle_overlays(self, event=None):
        """
        Toggle visibility of all overlays (annotations, regions, AIR, etc.).
        
        This method provides a unified way to show/hide overlays across different
        panel types. It toggles the overlays_visible flag and triggers a redraw.
        
        Subclasses should check self.overlays_visible in their draw_specialized_overlays()
        implementation to respect this toggle state.
        
        Args:
            event: Tkinter event object (optional, for keyboard binding)
        """
        self.overlays_visible = not self.overlays_visible
        
        # Clear all overlay-related canvas items
        self.canvas.delete("annotation")
        self.canvas.delete("region_visual")
        self.canvas.delete("air_visual")
        self.canvas.delete("air_drag")
        
        # Redraw image with overlays if visible
        if self.rawImage is not None:
            self.render_zoomed_image()  # This will call draw_specialized_overlays()
        
        # Update status if available
        status = "visible" if self.overlays_visible else "hidden"
        if hasattr(self.context, 'status_bar') and self.context.status_bar:
            self.context.status_bar.update(f"Overlays {status}", level="info")
