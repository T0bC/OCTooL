# -*- coding: utf-8 -*-
"""
Instruction Renderer for OCTexVIEW

This module provides a centralized system for rendering instruction text
on canvas widgets across different panels. It supports multi-column layouts,
color-coded sections, and visual symbols for better user guidance.

Created on Wed Oct 01 11:20:00 2025
@author: Tobias Meissner
"""

import tkinter as tk
from PIL import Image, ImageTk


class InstructionRenderer:
    """
    Renders instruction text on Tkinter canvas widgets with visual styling.
    
    Supports:
    - Multi-column layouts
    - Color-coded headers
    - Visual symbols/emojis
    - Hierarchical text organization
    - Logo placement
    """
    
    # Color scheme
    COLORS = {
        'header_region': '#FFD700',      # Gold for region boundaries
        'header_air': '#00E5FF',         # Cyan for AIR regions
        'header_navigation': '#A5D6A7',  # Green for navigation
        'header_workflow': '#CE93D8',    # Purple for workflow
        'header_settings': '#FFAB91',    # Orange for settings
        'symbol': '#90CAF9',             # Light blue for symbols
        'text_primary': '#D0D0D0',       # Light gray for main text
        'text_secondary': '#B0B0B0',     # Dimmer gray for sub-text
        'text_tertiary': '#909090',      # Even dimmer for hints
    }
    
    # Font configuration
    FONTS = {
        'header': 'Sans 12 bold',
        'text': 'Sans 10',
        'symbol': 'Sans 14',
        'small': 'Sans 9',
    }
    
    @staticmethod
    def render_image_viewer_instructions(canvas, canvas_width, canvas_height, logo_image=None):
        """
        Render instructions for the image viewer panel.
        
        Args:
            canvas: Tkinter canvas widget
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
            logo_image: Optional PIL ImageTk.PhotoImage for logo display
        """
        canvas.delete("all")
        
        # Draw logo if provided
        if logo_image:
            canvas.create_image(canvas_width - 217 // 2 - 7, 45, image=logo_image)
        
        # Layout configuration
        left_col_x = 20
        right_col_x = canvas_width // 2 + 20
        start_y = 100
        line_spacing = 22
        
        # === LEFT COLUMN: Region Selection ===
        y = start_y
        
        # Header
        canvas.create_text(left_col_x, y, fill=InstructionRenderer.COLORS['header_region'],
                          font=InstructionRenderer.FONTS['header'],
                          text="◆ REGION BOUNDARIES", anchor=tk.NW, tags="Text")
        y += line_spacing + 5
        
        # Instructions
        instructions_left = [
            ("🖱️", "Click twice to define vertical boundaries"),
            ("", "  • First click: Start boundary"),
            ("", "  • Second click: End boundary"),
            ("", ""),
            ("📋", "First region: Applied to ALL slices"),
            ("✏️", "Subsequent edits: Current slice only"),
            ("", ""),
            ("🎨", "Visual: Yellow vertical lines"),
        ]
        
        y = InstructionRenderer._render_instruction_list(
            canvas, left_col_x, y, instructions_left, line_spacing
        )
        
        # === RIGHT COLUMN: AIR Selection ===
        y = start_y
        
        # Header
        canvas.create_text(right_col_x, y, fill=InstructionRenderer.COLORS['header_air'],
                          font=InstructionRenderer.FONTS['header'],
                          text="◆ AIR REGIONS", anchor=tk.NW, tags="Text")
        y += line_spacing + 5
        
        # Instructions
        instructions_right = [
            ("🖱️", "Click and drag to define rectangle"),
            ("", "  • Drag: Area of Interest Rectangle"),
            ("", "  • Release: Confirm selection"),
            ("", ""),
            ("📋", "First AIR: Applied to ALL slices"),
            ("✏️", "Subsequent edits: Current slice only"),
            ("", ""),
            ("🎨", "Visual: Cyan rectangle"),
        ]
        
        y = InstructionRenderer._render_instruction_list(
            canvas, right_col_x, y, instructions_right, line_spacing
        )
        
        # === BOTTOM: Navigation Controls ===
        bottom_y = canvas_height - 80
        center_x = canvas_width // 2
        
        canvas.create_text(center_x, bottom_y, fill=InstructionRenderer.COLORS['header_navigation'],
                          font=InstructionRenderer.FONTS['header'],
                          text="⌨ NAVIGATION", anchor=tk.N, tags="Text")
        
        nav_text = "← → Arrow Keys: Navigate slices  |  Mouse Wheel: Navigate slices  |  Ctrl+Wheel: Zoom  |  Ctrl+Drag: Pan  |  H: Toggle overlays"
        canvas.create_text(center_x, bottom_y + 25, fill=InstructionRenderer.COLORS['text_tertiary'],
                          font=InstructionRenderer.FONTS['text'],
                          text=nav_text, anchor=tk.N, tags="Text")
    
    @staticmethod
    def render_load_panel_instructions(canvas, canvas_width, canvas_height, logo_image=None):
        """
        Render instructions for the load/folder selection panel.
        
        Args:
            canvas: Tkinter canvas widget
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
            logo_image: Optional PIL ImageTk.PhotoImage for logo display
        """
        canvas.delete("all")
        
        # Draw logo if provided
        if logo_image:
            canvas.create_image(canvas_width - 217 // 2 - 7, 45, image=logo_image)
        
        # Center layout for workflow instructions
        center_x = canvas_width // 2
        start_y = 120
        line_spacing = 24
        
        # Main header
        canvas.create_text(center_x, start_y, fill=InstructionRenderer.COLORS['header_workflow'],
                          font=InstructionRenderer.FONTS['header'],
                          text="◆ CARL QUANT WORKFLOW", anchor=tk.N, tags="Text")
        
        y = start_y + 40
        
        # Workflow steps
        workflow_steps = [
            ("1️⃣", "Select Folder", "Choose a directory containing OCT image stacks"),
            ("", "", "  • Each subfolder = one specimen"),
            ("", "", "  • Supported formats: .jpg, .png, .tif, .tiff"),
            ("", "", ""),
            ("2️⃣", "Configure Regions", "Define analysis regions on images"),
            ("", "", "  • Region boundaries: Vertical lines (click twice)"),
            ("", "", "  • AIR regions: Rectangles (click and drag)"),
            ("", "", ""),
            ("3️⃣", "Start Analysis", "Process all configured specimens"),
            ("", "", "  • Results saved to Data_[operator]_[measurement] folder"),
            ("", "", "  • Configuration auto-saved for future sessions"),
        ]
        
        for number, title, description in workflow_steps:
            if not number and not title:
                # Empty line for spacing
                y += line_spacing // 2
                continue
            
            if number:
                # Step number
                canvas.create_text(center_x - 200, y, fill=InstructionRenderer.COLORS['symbol'],
                                  font=InstructionRenderer.FONTS['symbol'],
                                  text=number, anchor=tk.W, tags="Text")
                # Step title
                canvas.create_text(center_x - 165, y, fill=InstructionRenderer.COLORS['text_primary'],
                                  font=InstructionRenderer.FONTS['header'],
                                  text=title, anchor=tk.W, tags="Text")
            
            if description:
                # Description text
                text_x = center_x - 165 if number else center_x - 165
                canvas.create_text(text_x, y + (18 if number else 0),
                                  fill=InstructionRenderer.COLORS['text_secondary'],
                                  font=InstructionRenderer.FONTS['text'],
                                  text=description, anchor=tk.W, tags="Text")
            
            y += line_spacing
    
    @staticmethod
    def render_settings_panel_instructions(canvas, canvas_width, canvas_height, logo_image=None):
        """
        Render instructions for the settings/configuration panel.
        
        Args:
            canvas: Tkinter canvas widget
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
            logo_image: Optional PIL ImageTk.PhotoImage for logo display
        """
        canvas.delete("all")
        
        # Draw logo if provided
        if logo_image:
            canvas.create_image(canvas_width - 217 // 2 - 7, 45, image=logo_image)
        
        center_x = canvas_width // 2
        start_y = 120
        line_spacing = 22
        
        # Main header
        canvas.create_text(center_x, start_y, fill=InstructionRenderer.COLORS['header_settings'],
                          font=InstructionRenderer.FONTS['header'],
                          text="◆ ANALYSIS SETTINGS", anchor=tk.N, tags="Text")
        
        y = start_y + 40
        
        # Settings information
        settings_info = [
            ("⚙️", "Configure analysis parameters before processing"),
            ("", ""),
            ("📊", "Region Configuration"),
            ("", "  • Number of sound regions"),
            ("", "  • Number of lesion regions"),
            ("", "  • Region width and spacing"),
            ("", ""),
            ("🔬", "Analysis Parameters"),
            ("", "  • Surface detection threshold"),
            ("", "  • Depth calculation method"),
            ("", "  • Statistical measures"),
            ("", ""),
            ("💾", "Output Settings"),
            ("", "  • Operator name"),
            ("", "  • Measurement number"),
            ("", "  • Export format preferences"),
        ]
        
        y = InstructionRenderer._render_instruction_list(
            canvas, center_x - 200, y, settings_info, line_spacing
        )
    
    @staticmethod
    def _render_instruction_list(canvas, x, y, instructions, line_spacing):
        """
        Helper method to render a list of instructions with symbols.
        
        Args:
            canvas: Tkinter canvas widget
            x: X coordinate for text start
            y: Y coordinate for text start
            instructions: List of (symbol, text) tuples
            line_spacing: Vertical spacing between lines
        
        Returns:
            Final y coordinate after rendering
        """
        for symbol, text in instructions:
            if text == "":
                y += line_spacing // 2
                continue
            
            if symbol:
                # Render symbol
                canvas.create_text(x, y, fill=InstructionRenderer.COLORS['symbol'],
                                  font=InstructionRenderer.FONTS['symbol'],
                                  text=symbol, anchor=tk.NW, tags="Text")
                # Render main text
                canvas.create_text(x + 25, y, fill=InstructionRenderer.COLORS['text_primary'],
                                  font=InstructionRenderer.FONTS['text'],
                                  text=text, anchor=tk.NW, tags="Text")
            else:
                # Render sub-text without symbol
                canvas.create_text(x + 25, y, fill=InstructionRenderer.COLORS['text_secondary'],
                                  font=InstructionRenderer.FONTS['text'],
                                  text=text, anchor=tk.NW, tags="Text")
            
            y += line_spacing
        
        return y
    
    @staticmethod
    def load_logo(logo_path, size=(217, 76)):
        """
        Load and resize logo image for display.
        
        Args:
            logo_path: Path to logo image file
            size: Tuple of (width, height) for resizing
        
        Returns:
            ImageTk.PhotoImage object or None if loading fails
        """
        try:
            logo = Image.open(logo_path)
            logo = logo.resize(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(logo)
        except Exception:
            return None
