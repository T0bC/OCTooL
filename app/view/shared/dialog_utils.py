#!/usr/bin/env python3
"""
Dialog Utilities.

Shared building blocks for the small Toplevel dialogs: window centering, the
themed modal shell used by the About and Help dialogs, a scrolled read-only
text area, and the standard Close button.

Key contents:
- center_on_parent: Centers a dialog over its parent window.
- center_on_screen: Sizes a dialog and centers it on the screen.
- create_themed_dialog: Modal Toplevel with theme background and padded main frame.
- create_scrolled_text: Text widget with a scrollbar, styled with theme input colors.
- add_close_button: Close button (right-aligned) with Escape binding and focus.

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
from tkinter import ttk


def center_on_parent(dialog, parent):
    """Center the dialog on the parent window."""
    dialog.update_idletasks()

    # Get parent position and size
    parent_x = parent.winfo_x()
    parent_y = parent.winfo_y()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()

    # Get dialog size
    dialog_width = dialog.winfo_width()
    dialog_height = dialog.winfo_height()

    # Calculate center position
    x = parent_x + (parent_width - dialog_width) // 2
    y = parent_y + (parent_height - dialog_height) // 2

    dialog.geometry(f"+{x}+{y}")


def center_on_screen(dialog, width, height):
    """Give the dialog the given size and center it on the screen."""
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    dialog.geometry(f"{width}x{height}+{x}+{y}")


def create_themed_dialog(parent, style, title, width, height):
    """Create a modal, screen-centered, theme-colored dialog with a main frame.

    Returns:
        tuple: (dialog, main_frame) where main_frame is padded and packed to fill.
    """
    # Create modal dialog
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent)
    dialog.grab_set()

    # Set size and center the dialog
    center_on_screen(dialog, width, height)

    # Apply dark theme colors
    dialog.configure(bg=style.colors.bg)

    # Main frame
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    return dialog, main_frame


def create_scrolled_text(parent, style, *, font, padding, frame_pack_kwargs):
    """Create a text widget with a scrollbar inside a new frame.

    Args:
        parent: Container for the text frame
        style: ttkbootstrap Style object (supplies input colors)
        font: Font tuple for the text widget
        padding: Internal padx/pady of the text widget
        frame_pack_kwargs: Keyword arguments for packing the surrounding frame

    Returns:
        tk.Text: The text widget (caller inserts content and disables it).
    """
    text_frame = ttk.Frame(parent)
    text_frame.pack(**frame_pack_kwargs)

    scrollbar = ttk.Scrollbar(text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    text_widget = tk.Text(
        text_frame,
        wrap=tk.WORD,
        font=font,
        bg=style.colors.inputbg,
        fg=style.colors.inputfg,
        relief=tk.FLAT,
        padx=padding,
        pady=padding,
        yscrollcommand=scrollbar.set,
    )
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=text_widget.yview)

    return text_widget


def add_close_button(dialog, button_frame):
    """Add a right-aligned Close button, bind Escape to close, and focus it."""
    close_btn = ttk.Button(
        button_frame, text="Close", bootstyle="secondary", command=dialog.destroy
    )
    close_btn.pack(side=tk.RIGHT)

    # Bind Escape key to close
    dialog.bind("<Escape>", lambda e: dialog.destroy())

    # Focus on close button
    close_btn.focus_set()

    return close_btn
