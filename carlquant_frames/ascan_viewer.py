#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A-Scan Viewer Module

Provides a non-blocking popup window to display A-Scan data for selected rows.

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils.error_handler import handle_errors


class AScanViewer:
    """Manages A-Scan viewer popup window."""
    
    def __init__(self, parent, style, row_data=None):
        """
        Initialize the AScanViewer.
        
        Args:
            parent: Parent tkinter window
            style: ttkbootstrap Style object for theming
            row_data: Data from the selected row (optional)
        """
        self.parent = parent
        self.style = style
        self.row_data = row_data
        self.dialog = None
    
    @handle_errors("AScanViewer.show")
    def show(self):
        """Show the A-Scan viewer dialog (non-blocking)."""
        # Create non-modal dialog (no grab_set() for non-blocking behavior)
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("A-Scan Viewer")
        self.dialog.transient(self.parent)
        # NOTE: No grab_set() to keep it non-blocking
        
        # Set size and position
        dialog_width = 800
        dialog_height = 600
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
        
        # Title label
        title_label = ttk.Label(
            main_frame,
            text="A-Scan Viewer",
            font=('Segoe UI', 14, 'bold'),
            bootstyle="inverse-dark"
        )
        title_label.pack(pady=(0, 15))
        
        # Content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Display placeholder text for now
        text_widget = tk.Text(
            content_frame,
            wrap=tk.WORD,
            font=('Consolas', 11),
            bg=self.style.colors.inputbg,
            fg=self.style.colors.inputfg,
            relief=tk.FLAT,
            padx=20,
            pady=20
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Insert placeholder content
        placeholder_text = "A-Scan Viewer\n\n"
        placeholder_text += "This window will display detailed A-Scan data.\n\n"
        
        if self.row_data:
            placeholder_text += f"Selected Row Data:\n{self.row_data}\n\n"
        
        placeholder_text += "Further functionality will be developed here."
        
        text_widget.insert('1.0', placeholder_text)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Close button
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            bootstyle="secondary",
            command=self.dialog.destroy
        )
        close_btn.pack(side=tk.RIGHT)
        
        # Bind Escape key to close
        self.dialog.bind('<Escape>', lambda e: self.dialog.destroy())
        
        # Focus on close button
        close_btn.focus_set()
    
    def destroy(self):
        """Close the dialog window."""
        if self.dialog:
            self.dialog.destroy()
