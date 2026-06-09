# -*- coding: utf-8 -*-
"""
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
import json
from PIL import Image, ImageTk
from app.logic.shared.paths import resource_path


class InstructionRenderer:
    """
    Data-driven instruction renderer for application panels.
    
    Renders instructions from JSON configuration files onto canvas widgets.
    Automatically adapts layout based on available vertical space with column
    overflow support to ensure all content is visible without scrolling.
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
        'header': 'Sans 13 bold',
        'text': 'Sans 11',
        'symbol': 'Sans 14',
        'small': 'Sans 10',
        'step_title': 'Sans 11 bold',
        'step_number': 'Sans 10 bold',
    }
    
    def __init__(self, canvas, instructions_file="assets/instructions.json"):
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
            instructions_path = resource_path(self.instructions_file)
            with open(instructions_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Instructions file not found: {instructions_path}")
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
        
        # Force canvas to update to get accurate dimensions
        self.canvas.update_idletasks()
        
        # Get canvas dimensions, fallback to configured dimensions if not yet rendered
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # If canvas hasn't been rendered yet, use configured dimensions
        if canvas_width <= 1:
            canvas_width = self.canvas.winfo_reqwidth()
        if canvas_height <= 1:
            canvas_height = self.canvas.winfo_reqheight()
        
        # Draw logo if available
        if self.logo_image:
            self.canvas.create_image(canvas_width - 217 // 2 - 7, 45, image=self.logo_image)
        
        # Get instruction data and render
        data = self.instructions_data[instruction_key]
        layout = data.get('layout', 'comprehensive_guide')
        
        # Currently only 'comprehensive_guide' layout is supported
        if layout == 'comprehensive_guide':
            self._render_comprehensive_guide(data, canvas_width, canvas_height)
        else:
            self._render_error(f"Unsupported layout: '{layout}'. Only 'comprehensive_guide' is supported.")
    
    def _calculate_workflow_height(self, data, line_spacing=19, section_spacing=10):
        """
        Calculate the required height for rendering workflow steps.
        
        Args:
            data: Instruction data dictionary
            line_spacing: Spacing between lines
            section_spacing: Spacing between sections
            
        Returns:
            Required height in pixels
        """
        height = 0
        if 'workflow_steps' in data:
            for step in data['workflow_steps']:
                height += line_spacing  # Step number and title
                if 'panel' in step:
                    height += line_spacing - 2  # Panel location
                if 'actions' in step:
                    height += len(step['actions']) * (line_spacing - 4)  # Actions
                height += section_spacing  # Space between steps
        return height
    
    def _render_comprehensive_guide(self, data, canvas_width, canvas_height):
        """
        Render comprehensive getting started guide with workflow, tips, and panel locations.
        Automatically adapts layout based on available vertical space:
        - Workflow steps fill column 1 first
        - If they overflow, continue in column 2
        - Quick Tips and Panel Guide appear below overflow content in column 2
        """
        # Layout configuration
        left_margin = 15
        start_y = 50
        line_spacing = 19
        section_spacing = 10
        
        # Calculate required height for workflow steps
        workflow_height = self._calculate_workflow_height(data, line_spacing, section_spacing)
        available_height = canvas_height - start_y - 40  # Reserve space for title and bottom margin
        
        # Title
        if 'title' in data:
            title = data['title']
            color = self.COLORS.get(title.get('color', 'text_primary'))
            self.canvas.create_text(canvas_width // 2, 20, fill=color,
                                   font=self.FONTS['header'],
                                   text=title['text'], anchor=tk.N, tags="Text")
        
        # Always use adaptive two-column layout with overflow support
        self._render_adaptive_two_column_layout(data, canvas_width, canvas_height, start_y, line_spacing, section_spacing, left_margin, available_height)
    
    def _render_adaptive_two_column_layout(self, data, canvas_width, canvas_height, start_y, line_spacing, section_spacing, left_margin, available_height):
        """
        Adaptive two-column layout with overflow support.
        Workflow steps fill column 1, overflow to column 2.
        Quick Tips and Panel Guide appear below overflow in column 2.
        """
        col1_x = left_margin
        col2_x = canvas_width // 2 + 10
        col1_y = start_y
        col2_y = start_y
        
        # Render workflow steps with overflow detection
        if 'workflow_steps' in data:
            steps = data['workflow_steps']
            current_column = 1
            
            for step in steps:
                number = step.get('number', '')
                title = step.get('title', '')
                
                # Calculate height needed for this step
                step_height = line_spacing  # Title
                if 'panel' in step:
                    step_height += line_spacing - 2
                if 'actions' in step:
                    step_height += len(step['actions']) * (line_spacing - 4)
                step_height += section_spacing
                
                # Check if we need to switch to column 2
                # Only switch if the ENTIRE step won't fit (with small margin for safety)
                if current_column == 1 and (col1_y - start_y + step_height) > (available_height + 50):
                    current_column = 2
                
                # Select current position
                if current_column == 1:
                    col_x = col1_x
                    y = col1_y
                else:
                    col_x = col2_x
                    y = col2_y
                
                # Render step number with symbol
                number_text = f"◉ {number}."
                self.canvas.create_text(col_x, y, fill=self.COLORS['symbol'],
                                       font=self.FONTS['step_number'],
                                       text=number_text, anchor=tk.NW, tags="Text")
                
                # Render title
                self.canvas.create_text(col_x + 30, y, fill=self.COLORS['text_primary'],
                                       font=self.FONTS['step_title'],
                                       text=title, anchor=tk.NW, tags="Text")
                y += line_spacing
                
                # Panel location
                if 'panel' in step:
                    self.canvas.create_text(col_x + 5, y, fill=self.COLORS['text_tertiary'],
                                           font=self.FONTS['small'],
                                           text=f"📍 {step['panel']}", anchor=tk.NW, tags="Text")
                    y += line_spacing - 2
                
                # Actions
                if 'actions' in step:
                    for action in step['actions']:
                        self.canvas.create_text(col_x + 10, y, fill=self.COLORS['text_secondary'],
                                               font=self.FONTS['small'],
                                               text=action, anchor=tk.NW, tags="Text")
                        y += line_spacing - 4
                
                y += section_spacing
                
                # Update column position
                if current_column == 1:
                    col1_y = y
                else:
                    col2_y = y
        
        # Add extra spacing before Quick Tips
        col2_y += section_spacing * 2
        
        # === Quick Tips Section (in column 2, below overflow content) ===
        if 'quick_tips' in data:
            tips_data = data['quick_tips']
            
            # Header
            self.canvas.create_text(col2_x, col2_y, fill=self.COLORS['header_navigation'],
                                   font='Sans 10 bold',
                                   text=tips_data.get('header', 'QUICK TIPS'),
                                   anchor=tk.NW, tags="Text")
            col2_y += line_spacing + 3
            
            # Tips in single column (simplified for space efficiency)
            if 'tips' in tips_data:
                for tip in tips_data['tips']:
                    self.canvas.create_text(col2_x + 5, col2_y,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['small'],
                                           text=tip, anchor=tk.NW, tags="Text")
                    col2_y += line_spacing - 4
            
            col2_y += section_spacing + 5
        
        # === Panel Guide Section (in column 2, below Quick Tips) ===
        if 'panel_guide' in data:
            guide_data = data['panel_guide']
            
            # Header
            self.canvas.create_text(col2_x, col2_y, fill=self.COLORS['header_settings'],
                                   font='Sans 10 bold',
                                   text=guide_data.get('header', 'PANEL LOCATIONS'),
                                   anchor=tk.NW, tags="Text")
            col2_y += line_spacing + 3
            
            # Panel locations
            if 'panels' in guide_data:
                for panel in guide_data['panels']:
                    panel_text = f"{panel.get('name', '')}: {panel.get('location', '')}"
                    self.canvas.create_text(col2_x + 5, col2_y,
                                           fill=self.COLORS['text_secondary'],
                                           font=self.FONTS['small'],
                                           text=panel_text, anchor=tk.NW, tags="Text")
                    col2_y += line_spacing - 4
    
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
