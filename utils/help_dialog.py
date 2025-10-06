#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Help Dialog Module

Provides context-aware help dialogs for OCTexVIEW application.
Shows tab-specific quick guides and provides access to full documentation.

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk
import webbrowser
import os
from utils.error_handler import handle_errors


class HelpDialog:
    """Manages help dialogs and documentation access for OCTexVIEW."""
    
    def __init__(self, parent, style, current_tab=0):
        """
        Initialize the HelpDialog.
        
        Args:
            parent: Parent tkinter window
            style: ttkbootstrap Style object for theming
            current_tab: Index of currently active tab (0=Export, 1=Analyze, 2=CarlQuant)
        """
        self.parent = parent
        self.style = style
        self.current_tab = current_tab
        
        # Define help messages for each tab based on instructions.json
        self.help_messages = {
            0: {  # Export tab
                'title': '◆ EXPORT - QUICK GUIDE',
                'content': (
                    '1. LOAD IMAGES\n'
                    '   ▸ Select source folder with Thorlabs OCT files\n'
                    '   ▸ Preview loaded image stack\n'
                    '   ▸ Verify image count and format\n\n'
                    '2. CONFIGURE GLOBAL SETTINGS\n'
                    '   ▸ Set output resolution\n'
                    '   ▸ Choose export format (PNG, TIFF, etc.)\n'
                    '   ▸ Configure compression settings\n\n'
                    '3. CUSTOMIZE PER-IMAGE\n'
                    '   ▸ Add text overlays\n'
                    '   ▸ Set scale bars\n'
                    '   ▸ Configure annotations\n\n'
                    '4. EXECUTE EXPORT\n'
                    '   ▸ Review export settings\n'
                    '   ▸ Click "Start Export" button\n'
                    '   ▸ Monitor progress\n\n'
                    '💡 QUICK TIPS\n'
                    '   ◄ ► Navigate images  |  ⊕ Preview before export\n'
                    '   📁 Batch process folders  |  ⚙️ Save settings presets'
                )
            },
            1: {  # Analyze tab
                'title': '◆ ANALYZE - QUICK GUIDE',
                'content': (
                    '1. LOAD DATA\n'
                    '   ▸ Click "Load Folder" to select data directory\n'
                    '   ▸ Browse and select image stack\n'
                    '   ▸ Data loads into image viewer\n\n'
                    '2. ANNOTATE IMAGES\n'
                    '   ▸ Click on image to add annotation points\n'
                    '   ▸ Drag points to adjust position\n'
                    '   ▸ Use keyboard shortcuts for navigation\n\n'
                    '3. ADD COLUMNS\n'
                    '   ▸ Define custom data columns\n'
                    '   ▸ Set column types (numeric, text, boolean)\n'
                    '   ▸ Add metadata for analysis\n\n'
                    '4. EXPORT DATA\n'
                    '   ▸ Configure export settings\n'
                    '   ▸ Select output format\n'
                    '   ▸ Save annotated data\n\n'
                    '💡 QUICK TIPS\n'
                    '   ◄ ► Navigate frames  |  ⊕ Ctrl+Wheel: Zoom\n'
                    '   ✋ Drag points to adjust  |  ⌨ H key: Toggle annotations'
                )
            },
            2: {  # CarlQuant tab
                'title': '◆ CARL QUANT - QUICK GUIDE',
                'content': (
                    '1. LOAD IMAGES\n'
                    '   ▸ Click "Select Folder" button\n'
                    '   ▸ Choose directory with OCT image stacks\n'
                    '   ▸ Each subfolder = one specimen\n\n'
                    '2. REVIEW SPECIMENS\n'
                    '   ▸ View loaded specimens in table\n'
                    '   ▸ Click specimen to select\n'
                    '   ▸ Check slice count and status\n\n'
                    '3. DEFINE REGIONS\n'
                    '   ▸ REGION: Click twice for vertical boundaries\n'
                    '   ▸ AIR: Click & drag for rectangle\n'
                    '   ▸ First definition applies to ALL slices\n\n'
                    '4. CONFIGURE SETTINGS\n'
                    '   ▸ Set operator name & measurement #\n'
                    '   ▸ Configure region parameters\n'
                    '   ▸ Adjust analysis settings\n\n'
                    '5. START ANALYSIS\n'
                    '   ▸ Click "Start Analyzing" button\n'
                    '   ▸ Results saved to Data_[operator]_[measurement]\n'
                    '   ▸ Configuration auto-saved\n\n'
                    '💡 QUICK TIPS\n'
                    '   ◄ ► Navigate slices  |  ⊕ Ctrl+Wheel: Zoom\n'
                    '   ✋ Ctrl+Drag: Pan  |  ⌨ H key: Toggle overlays'
                )
            }
        }
    
    @handle_errors("HelpDialog.show")
    def show(self):
        """Show the help dialog for the current tab."""
        current_help = self.help_messages.get(self.current_tab, self.help_messages[0])
        self._create_dialog(current_help['title'], current_help['content'])
    
    @handle_errors("HelpDialog.create_dialog")
    def _create_dialog(self, title, content):
        """Create a custom dark-themed help dialog."""
        # Create modal dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(title)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Set size and center the dialog
        dialog_width = 600
        dialog_height = 550
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
        
        # Title label
        title_label = ttk.Label(
            main_frame,
            text=title,
            font=('Segoe UI', 12, 'bold'),
            bootstyle="inverse-dark"
        )
        title_label.pack(pady=(0, 15))
        
        # Content text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Consolas', 10),
            bg=self.style.colors.inputbg,
            fg=self.style.colors.inputfg,
            relief=tk.FLAT,
            padx=15,
            pady=15,
            yscrollcommand=scrollbar.set
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        # Insert content
        text_widget.insert('1.0', content)
        text_widget.config(state=tk.DISABLED)  # Make read-only
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Full documentation button
        docs_btn = ttk.Button(
            button_frame,
            text="📖 View Full Documentation",
            bootstyle="info",
            command=lambda: [self.open_documentation(), dialog.destroy()]
        )
        docs_btn.pack(side=tk.LEFT, padx=(0, 10))
        
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
    
    @handle_errors("HelpDialog.open_documentation")
    def open_documentation(self):
        """Open the full HTML documentation in the default browser."""
        # Look for documentation file in the application directory
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Alternative common documentation filenames and locations
        doc_alternatives = [
            os.path.join('HTML_docs', 'OCTexVIEW_MANUAL.html'),  # Primary location
            'OCTexVIEW_MANUAL.html',
            'documentation.html',
            'docs.html',
            'help.html',
            'index.html',
            'README.html'
        ]
        
        # Try to find the documentation file
        found_doc = None
        for doc_path in doc_alternatives:
            test_path = os.path.join(app_dir, doc_path)
            if os.path.exists(test_path):
                found_doc = test_path
                break
        
        if found_doc:
            webbrowser.open('file://' + found_doc)
        else:
            tk.messagebox.showwarning(
                title='Documentation Not Found',
                message=f'Could not find documentation file in:\n{app_dir}\n\n'
                        f'Expected one of: {", ".join(doc_alternatives)}'
            )
