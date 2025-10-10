#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Help Dialog Module

Provides context-aware help dialogs for OCTexVIEW application.
Shows tab-specific quick guides and provides access to full documentation.

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
import webbrowser
import os
import json
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
        
        # Map tab indices to instruction keys
        self.tab_to_instruction_key = {
            0: 'export_getting_started',
            1: 'analyze_getting_started',
            2: 'carlquant_getting_started'
        }
        
        # Load instructions from JSON file
        self.instructions = self._load_instructions()
    
    @handle_errors("HelpDialog._load_instructions")
    def _load_instructions(self):
        """Load instructions from the instructions.json file."""
        try:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(app_dir, 'utils', 'instructions.json')
            
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load instructions.json: {e}")
            # Return empty dict as fallback
            return {}
    
    def _format_help_content(self, instruction_key):
        """Format the instruction data into help dialog content.
        
        Args:
            instruction_key: Key for the instruction section (e.g., 'carlquant_getting_started')
            
        Returns:
            dict: Dictionary with 'title' and 'content' keys
        """
        if not self.instructions or instruction_key not in self.instructions:
            return {
                'title': '◆ HELP - QUICK GUIDE',
                'content': 'Help content not available. Please check instructions.json file.'
            }
        
        instruction = self.instructions[instruction_key]
        title = instruction.get('title', {}).get('text', '◆ QUICK GUIDE')
        
        # Build content from workflow steps
        content_parts = []
        
        for step in instruction.get('workflow_steps', []):
            step_num = step.get('number', '?')
            step_title = step.get('title', 'Step').upper()
            content_parts.append(f"{step_num}. {step_title}")
            
            for action in step.get('actions', []):
                content_parts.append(f"   {action}")
            
            content_parts.append("")  # Empty line between steps
        
        # Add quick tips if available
        quick_tips = instruction.get('quick_tips', {})
        if quick_tips:
            tips_header = quick_tips.get('header', '💡 QUICK TIPS')
            content_parts.append(tips_header)
            
            tips = quick_tips.get('tips', [])
            # Format tips in two columns if possible
            for i in range(0, len(tips), 2):
                if i + 1 < len(tips):
                    content_parts.append(f"   {tips[i]}  |  {tips[i+1]}")
                else:
                    content_parts.append(f"   {tips[i]}")
        
        return {
            'title': title,
            'content': '\n'.join(content_parts)
        }
    
    @handle_errors("HelpDialog.show")
    def show(self):
        """Show the help dialog for the current tab."""
        instruction_key = self.tab_to_instruction_key.get(self.current_tab, 'export_getting_started')
        current_help = self._format_help_content(instruction_key)
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
