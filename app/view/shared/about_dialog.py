#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
About Dialog Module

Provides About dialog with application information and changelog access.

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
import webbrowser
import os
from app.view.shared.error_handler import handle_errors
from app.logic.shared.paths import resource_path


class AboutDialog:
    """Manages About dialog and changelog access for OCTooL."""
    
    def __init__(self, parent, style, version):
        """
        Initialize the AboutDialog.
        
        Args:
            parent: Parent tkinter window
            style: ttkbootstrap Style object for theming
            version: Application version string
        """
        self.parent = parent
        self.style = style
        self.version = version
    
    @handle_errors("AboutDialog.show")
    def show(self):
        """Show the About dialog."""
        about_content = (
            f'OCTooL{self.version}\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            'DEVELOPED BY\n'
            '  • Tobias Meißner [1]\n'
            '  • Maximilian Bemmann [1]\n\n'
            'WITH CONTRIBUTION FROM\n'
            '  • Jonas Golde [2]\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            'AFFILIATIONS\n'
            '[1] Universität Leipzig\n'
            '    Poliklinik für Zahnerhaltung und\n'
            '    Parodontologie\n\n'
            '[2] Technische Universität Dresden\n'
            '    Medizinische Fakultät Carl Gustav Carus\n'
            '    Klinisches Sensoring und Monitoring\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            'ERROR REPORTS\n'
            '  📧 tobias.meissner@medizin.uni-leipzig.de'
        )
        
        self._create_dialog(about_content)
    
    @handle_errors("AboutDialog.create_dialog")
    def _create_dialog(self, content):
        """Create a custom dark-themed About dialog."""
        # Create modal dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(f'About OCTooL')
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Set size and center the dialog
        dialog_width = 550
        dialog_height = 500
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Apply dark theme colors
        bg_color = self.style.colors.bg
        dialog.configure(bg=bg_color)
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Content text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Segoe UI', 10),
            bg=self.style.colors.inputbg,
            fg=self.style.colors.inputfg,
            relief=tk.FLAT,
            padx=20,
            pady=20,
            yscrollcommand=scrollbar.set
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        # Insert content with center alignment
        text_widget.tag_configure("center", justify='center')
        text_widget.insert('1.0', content)
        text_widget.tag_add("center", "1.0", "end")
        text_widget.config(state=tk.DISABLED)  # Make read-only
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Changelog button
        changelog_btn = ttk.Button(
            button_frame,
            text="📋 View Changelog",
            bootstyle="info",
            command=lambda: self.open_changelog()
        )
        changelog_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Close button
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            bootstyle="secondary",
            command=dialog.destroy
        )
        close_btn.pack(side=tk.RIGHT)
        
        # Bind Escape key to close
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        
        # Focus on close button
        close_btn.focus_set()
    
    @handle_errors("AboutDialog.open_changelog")
    def open_changelog(self):
        """Open the changelog HTML file in the default browser."""
        # Try to find the changelog file using resource_path
        changelog_alternatives = [
            'HTML_docs/OCTooL_change_log.html',  # Primary location
            'OCTooL_change_log.html',
            'CHANGELOG.html',
        ]
        
        # Try to find the changelog file
        found_changelog = None
        for changelog_path in changelog_alternatives:
            try:
                test_path = resource_path(changelog_path)
                if os.path.exists(test_path):
                    found_changelog = test_path
                    break
            except Exception:
                continue
        
        if found_changelog:
            # Convert to absolute path and use file:// protocol
            abs_path = os.path.abspath(found_changelog)
            webbrowser.open('file://' + abs_path)
        else:
            tk.messagebox.showwarning(
                title='Changelog Not Found',
                message='Could not find OCTooL_change_log.html\n\n'
                        'Please ensure the HTML_docs folder is included in the distribution.'
            )
