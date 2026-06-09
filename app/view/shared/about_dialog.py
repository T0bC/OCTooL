#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
About Dialog.

Modal dialog displaying OCTooL version, authors, affiliations, and external
links (email, GitHub, server). Also provides a button to open the changelog.

Key contents:
- AboutDialog: Builds and shows a dark-themed About modal.
- show: Renders the dialog with formatted content.
- _create_dialog: Low-level dialog construction and centering logic.

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


import webbrowser
import tkinter as tk
from tkinter import ttk
from app.view.shared.error_handler import handle_errors
from app.logic.shared.doc_links import open_doc
from app.logic.shared.app_config import CHANGELOG_URL

SERVER_URL = "https://dentlab.medizin.uni-leipzig.de"
GITHUB_URL = "https://github.com/T0bC/OCTooL"
DOI = "DOI: <placeholder>"


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
            '  📧 tobias.meissner@medizin.uni-leipzig.de\n\n'
            '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
            'LINKS\n'
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
        dialog_height = 580
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
        text_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 15))
        
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

        # Clickable links
        def _add_link(label, url):
            tag = f"link_{label}"
            text_widget.insert('end', f"  {label}\n", (tag, "center"))
            text_widget.tag_configure(
                tag, foreground=self.style.colors.info, underline=True
            )
            text_widget.tag_bind(tag, '<Button-1>',
                                  lambda e, u=url: webbrowser.open(u))
            text_widget.tag_bind(tag, '<Enter>',
                                  lambda e: text_widget.config(cursor='hand2'))
            text_widget.tag_bind(tag, '<Leave>',
                                  lambda e: text_widget.config(cursor=''))

        _add_link("🌐 dentlab.medizin.uni-leipzig.de", SERVER_URL)
        _add_link("💻 github.com/T0bC/OCTooL", GITHUB_URL)
        text_widget.insert('end', f"\n  {DOI}", "center")

        text_widget.config(state=tk.DISABLED)  # Make read-only
        
        # Button frame (packed at the bottom first so it stays visible)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
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
        """Open the changelog: server URL first, bundled HTML as offline fallback."""
        local_alternatives = [
            'HTML_docs/OCTooL_change_log.html',  # Primary local location
            'OCTooL_change_log.html',
            'CHANGELOG.html',
        ]

        if not open_doc(CHANGELOG_URL, local_alternatives):
            tk.messagebox.showwarning(
                title='Changelog Not Available',
                message='Could not reach the online changelog and no local copy '
                        'was found.\n\nCheck your internet connection or ensure '
                        'the HTML_docs folder is included in the distribution.'
            )
