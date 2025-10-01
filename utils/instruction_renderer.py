# -*- coding: utf-8 -*-
"""
Instruction Renderer for Carl Quant Module

This module provides a data-driven instruction rendering system that displays
contextual help on a shared canvas. Instructions are loaded from JSON files,
separating content from presentation logic.

Created on Wed Oct 01 11:48:00 2025
@author: Tobias Meissner
"""

import tkinter as tk
import json
from pathlib import Path
from PIL import Image, ImageTk


class InstructionRenderer:
    """
    Data-driven instruction renderer for Carl Quant panels.
    
    Renders instructions from JSON configuration files onto a shared canvas.
    Supports multiple layouts: two-column, centered steps, single column.
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
    
    def __init__(self, canvas, instructions_file="utils/instructions.json"):
        """
        Initialize the instruction renderer.
        
        Args:
            canvas: Tkinter canvas widget for rendering
            instructions_file: Path to JSON file containing instruction data
        """
        self.canvas = canvas
        self.instructions_file = instructions_file
        self.instructions_data = self._load_instructions()
        self.logo_image = None
    
    def _load_instructions(self):
        """Load instruction data from JSON file with UTF-8 encoding."""
        try:
            with open(self.instructions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Instructions file not found: {self.instructions_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in instructions file: {e}")
            return {}
        except Exception as e:
            print(f"Error loading instructions: {e}")
            return {}
    
    def set_logo(self, logo_path, size=(217, 76)):
        """
        Load and set logo image.
        
        Args:
            logo_path: Path to logo image file
            size: Tuple of (width, height) for resizing
        """
        try:
            logo = Image.open(logo_path)
            logo = logo.resize(size, Image.Resampling.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(logo)
        except Exception as e:
            print(f"Error loading logo: {e}")
            self.logo_image = None
    
    def render(self, instruction_key):
        """
        Render instructions for a specific context.
        
        Args:
            instruction_key: Key in instructions.json (e.g., 'image_viewer', 'workflow', 'settings')
        """
        self.canvas.delete("all")
        
        if instruction_key not in self.instructions_data:
            self._render_error(f"No instructions found for '{instruction_key}'")
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Draw logo if available
        if self.logo_image:
            self.canvas.create_image(canvas_width - 217 // 2 - 7, 45, image=self.logo_image)
        
        # Get instruction data
        data = self.instructions_data[instruction_key]
        layout = data.get('layout', 'single_column')
        
        # Render based on layout type
        if layout == 'comprehensive_guide':
            self._render_comprehensive_guide(data, canvas_width, canvas_height)
        elif layout == 'two_column':
            self._render_two_column(data, canvas_width, canvas_height)
        elif layout == 'centered_steps':
            self._render_centered_steps(data, canvas_width, canvas_height)
        elif layout == 'single_column':
            self._render_single_column(data, canvas_width, canvas_height)
        else:
            self._render_error(f"Unknown layout: {layout}")
    
    def _render_comprehensive_guide(self, data, canvas_width, canvas_height):
        """
        Render comprehensive getting started guide with workflow, tips, and panel locations.
        Optimized for efficient space usage on a single screen.
        """
        # Layout configuration
        left_margin = 15
        col1_x = left_margin
        col2_x = canvas_width // 2 + 10
        start_y = 90
        line_spacing = 18
        section_spacing = 12
        
        # Title
        if 'title' in data:
            title = data['title']
            color = self.COLORS.get(title.get('color', 'text_primary'))
            self.canvas.create_text(canvas_width // 2, 20, fill=color,
                                   font=self.FONTS['header'],
                                   text=title['text'], anchor=tk.N, tags="Text")
        
        # === LEFT COLUMN: Workflow Steps ===
        y = start_y
        
        if 'workflow_steps' in data:
            for step in data['workflow_steps']:
                # Step number and title
                step_text = f"{step.get('number', '')} {step.get('title', '')}"
                self.canvas.create_text(col1_x, y, fill=self.COLORS['symbol'],
                                       font='Sans 10 bold',
                                       text=step_text, anchor=tk.NW, tags="Text")
                y += line_spacing
                
                # Panel location (in smaller, dimmer text)
                if 'panel' in step:
                    self.canvas.create_text(col1_x + 5, y, fill=self.COLORS['text_tertiary'],
                                           font=self.FONTS['small'],
                                           text=f"📍 {step['panel']}", anchor=tk.NW, tags="Text")
                    y += line_spacing - 2
                
                # Actions (compact list)
                if 'actions' in step:
                    for action in step['actions']:
                        self.canvas.create_text(col1_x + 10, y, fill=self.COLORS['text_secondary'],
                                               font=self.FONTS['small'],
                                               text=action, anchor=tk.NW, tags="Text")
                        y += line_spacing - 4
                
                y += section_spacing  # Space between steps
        
        # === RIGHT COLUMN: Quick Tips & Panel Guide ===
        y = start_y
        
        # Quick Tips Section
        if 'quick_tips' in data:
            tips_data = data['quick_tips']
            
            # Header
            self.canvas.create_text(col2_x, y, fill=self.COLORS['header_navigation'],
                                   font='Sans 10 bold',
                                   text=tips_data.get('header', 'QUICK TIPS'),
                                   anchor=tk.NW, tags="Text")
            y += line_spacing + 3
            
            # Tips in compact two-column layout within right column
            if 'tips' in tips_data:
                tips = tips_data['tips']
                tips_per_col = (len(tips) + 1) // 2
                
                # First sub-column
                temp_y = y
                for i, tip in enumerate(tips[:tips_per_col]):
                    self.canvas.create_text(col2_x + 5, temp_y,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['small'],
                                           text=tip, anchor=tk.NW, tags="Text")
                    temp_y += line_spacing - 4
                
                # Second sub-column
                temp_y = y
                sub_col2_x = col2_x + 180
                for tip in tips[tips_per_col:]:
                    self.canvas.create_text(sub_col2_x, temp_y,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['small'],
                                           text=tip, anchor=tk.NW, tags="Text")
                    temp_y += line_spacing - 4
                
                y = max(temp_y, y + (tips_per_col * (line_spacing - 4)))
            
            y += section_spacing + 5
        
        # Panel Guide Section
        if 'panel_guide' in data:
            guide_data = data['panel_guide']
            
            # Header
            self.canvas.create_text(col2_x, y, fill=self.COLORS['header_settings'],
                                   font='Sans 10 bold',
                                   text=guide_data.get('header', 'PANEL LOCATIONS'),
                                   anchor=tk.NW, tags="Text")
            y += line_spacing + 3
            
            # Panel locations
            if 'panels' in guide_data:
                for panel in guide_data['panels']:
                    panel_text = f"{panel.get('name', '')}: {panel.get('location', '')}"
                    self.canvas.create_text(col2_x + 5, y,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['small'],
                                           text=panel_text, anchor=tk.NW, tags="Text")
                    y += line_spacing - 4
        
        # === BOTTOM: Key Visual Indicators ===
        bottom_y = canvas_height - 35
        center_x = canvas_width // 2
        
        visual_text = "🎨 Visual Indicators: Yellow Lines = Region Boundaries  |  Cyan Rectangle = AIR Region"
        self.canvas.create_text(center_x, bottom_y, fill=self.COLORS['text_tertiary'],
                               font=self.FONTS['small'],
                               text=visual_text, anchor=tk.N, tags="Text")
    
    def _render_two_column(self, data, canvas_width, canvas_height):
        """Render two-column layout (e.g., for image viewer)."""
        left_col_x = 20
        right_col_x = canvas_width // 2 + 20
        start_y = 100
        line_spacing = 22
        
        # Left column
        if 'left_column' in data:
            left_data = data['left_column']
            y = start_y
            
            # Header
            if 'header' in left_data:
                header = left_data['header']
                color = self.COLORS.get(header.get('color', 'text_primary'))
                self.canvas.create_text(left_col_x, y, fill=color,
                                       font=self.FONTS['header'],
                                       text=header['text'], anchor=tk.NW, tags="Text")
                y += line_spacing + 5
            
            # Instructions
            if 'instructions' in left_data:
                self._render_instruction_list(left_col_x, y, left_data['instructions'], line_spacing)
        
        # Right column
        if 'right_column' in data:
            right_data = data['right_column']
            y = start_y
            
            # Header
            if 'header' in right_data:
                header = right_data['header']
                color = self.COLORS.get(header.get('color', 'text_primary'))
                self.canvas.create_text(right_col_x, y, fill=color,
                                       font=self.FONTS['header'],
                                       text=header['text'], anchor=tk.NW, tags="Text")
                y += line_spacing + 5
            
            # Instructions
            if 'instructions' in right_data:
                self._render_instruction_list(right_col_x, y, right_data['instructions'], line_spacing)
        
        # Footer (navigation)
        if 'footer' in data:
            footer = data['footer']
            bottom_y = canvas_height - 80
            center_x = canvas_width // 2
            
            if 'header' in footer:
                header = footer['header']
                color = self.COLORS.get(header.get('color', 'text_primary'))
                self.canvas.create_text(center_x, bottom_y, fill=color,
                                       font=self.FONTS['header'],
                                       text=header['text'], anchor=tk.N, tags="Text")
            
            if 'text' in footer:
                self.canvas.create_text(center_x, bottom_y + 25,
                                       fill=self.COLORS['text_tertiary'],
                                       font=self.FONTS['text'],
                                       text=footer['text'], anchor=tk.N, tags="Text")
    
    def _render_centered_steps(self, data, canvas_width, canvas_height):
        """Render centered workflow steps layout."""
        center_x = canvas_width // 2
        start_y = 120
        line_spacing = 24
        
        # Main header
        if 'header' in data:
            header = data['header']
            color = self.COLORS.get(header.get('color', 'text_primary'))
            self.canvas.create_text(center_x, start_y, fill=color,
                                   font=self.FONTS['header'],
                                   text=header['text'], anchor=tk.N, tags="Text")
        
        y = start_y + 40
        
        # Workflow steps
        if 'steps' in data:
            for step in data['steps']:
                # Step number
                if 'number' in step:
                    self.canvas.create_text(center_x - 200, y,
                                           fill=self.COLORS['symbol'],
                                           font=self.FONTS['symbol'],
                                           text=step['number'], anchor=tk.W, tags="Text")
                
                # Step title
                if 'title' in step:
                    self.canvas.create_text(center_x - 165, y,
                                           fill=self.COLORS['text_primary'],
                                           font=self.FONTS['header'],
                                           text=step['title'], anchor=tk.W, tags="Text")
                
                # Description
                if 'description' in step:
                    self.canvas.create_text(center_x - 165, y + 18,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['text'],
                                           text=step['description'], anchor=tk.W, tags="Text")
                
                y += line_spacing
                
                # Details
                if 'details' in step:
                    for detail in step['details']:
                        self.canvas.create_text(center_x - 165, y,
                                               fill=self.COLORS['text_secondary'],
                                               font=self.FONTS['text'],
                                               text=detail, anchor=tk.W, tags="Text")
                        y += line_spacing
                
                y += line_spacing // 2  # Extra spacing between steps
    
    def _render_single_column(self, data, canvas_width, canvas_height):
        """Render single column layout (e.g., for settings)."""
        center_x = canvas_width // 2
        start_y = 120
        line_spacing = 22
        
        # Main header
        if 'header' in data:
            header = data['header']
            color = self.COLORS.get(header.get('color', 'text_primary'))
            self.canvas.create_text(center_x, start_y, fill=color,
                                   font=self.FONTS['header'],
                                   text=header['text'], anchor=tk.N, tags="Text")
        
        y = start_y + 40
        
        # Sections
        if 'sections' in data:
            for section in data['sections']:
                symbol = section.get('symbol', '')
                text = section.get('text', '')
                
                if not text:
                    y += line_spacing // 2
                    continue
                
                if symbol:
                    # Render symbol
                    self.canvas.create_text(center_x - 200, y,
                                           fill=self.COLORS['symbol'],
                                           font=self.FONTS['symbol'],
                                           text=symbol, anchor=tk.W, tags="Text")
                    # Render main text
                    self.canvas.create_text(center_x - 175, y,
                                           fill=self.COLORS['text_primary'],
                                           font=self.FONTS['text'],
                                           text=text, anchor=tk.W, tags="Text")
                else:
                    # Render sub-text without symbol
                    self.canvas.create_text(center_x - 175, y,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['text'],
                                           text=text, anchor=tk.W, tags="Text")
                
                y += line_spacing
                
                # Subsections
                if 'subsections' in section:
                    for subsection in section['subsections']:
                        self.canvas.create_text(center_x - 175, y,
                                               fill=self.COLORS['text_secondary'],
                                               font=self.FONTS['text'],
                                               text=subsection, anchor=tk.W, tags="Text")
                        y += line_spacing
    
    def _render_instruction_list(self, x, y, instructions, line_spacing):
        """Helper to render a list of instructions."""
        for item in instructions:
            symbol = item.get('symbol', '')
            text = item.get('text', '')
            
            if not text:
                y += line_spacing // 2
                continue
            
            if symbol:
                # Render symbol
                self.canvas.create_text(x, y, fill=self.COLORS['symbol'],
                                       font=self.FONTS['symbol'],
                                       text=symbol, anchor=tk.NW, tags="Text")
                # Render main text
                self.canvas.create_text(x + 25, y, fill=self.COLORS['text_primary'],
                                       font=self.FONTS['text'],
                                       text=text, anchor=tk.NW, tags="Text")
            else:
                # Render sub-text without symbol
                self.canvas.create_text(x + 25, y, fill=self.COLORS['text_secondary'],
                                       font=self.FONTS['text'],
                                       text=text, anchor=tk.NW, tags="Text")
            
            y += line_spacing
        
        return y
    
    def _render_error(self, message):
        """Render error message on canvas."""
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        self.canvas.create_text(canvas_width // 2, canvas_height // 2,
                               fill="#FF5252",
                               font=self.FONTS['header'],
                               text=f"⚠️ {message}",
                               anchor=tk.CENTER, tags="Text")
    
    def clear(self):
        """Clear all instructions from canvas."""
        self.canvas.delete("all")
