# -*- coding: utf-8 -*-
"""
Error Handler.

Global error handling infrastructure: thread-safe popup windows, Tk callback
exception interception, and the @handle_errors decorator. Ensures no exception
fails silently, even in PyInstaller windowed builds where stderr is hidden.

Key contents:
- show_error_popup: Thread-safe popup that marshals onto the Tk main loop.
- _build_error_popup: Constructs the scrollable error dialog.
- install_tk_exception_handler: Hooks Tk's report_callback_exception globally.
- handle_errors: Decorator that catches, displays, and logs exceptions.

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


import threading
import traceback
import tkinter as tk
from tkinter import ttk

from app.logic.shared.logging_utils import log_error_to_file


def show_error_popup(title, message):
    """
    Displays a custom Tkinter popup window with a scrollable, selectable text area.

    Tkinter is not thread-safe. If this is called from a worker thread, the
    popup is marshalled onto the main loop via ``root.after`` so it never
    crashes the interpreter. On the main thread it is built directly.

    Args:
        title (str): Title of the popup window.
        message (str): Error message and traceback to display.
    """
    root = tk._default_root  # Get the default root window
    if root is None:
        root = tk.Tk()  # Create one if it doesn't exist

    # If we're off the main thread, schedule the popup on the GUI thread.
    if threading.current_thread() is not threading.main_thread():
        root.after(0, lambda: _build_error_popup(root, title, message))
        return

    _build_error_popup(root, title, message)


def _build_error_popup(root, title, message):
    """Build and show the error popup. Must run on the Tk main thread."""
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.geometry("600x400")
    popup.resizable(True, True)
    popup.transient(root)  # Keep popup on top of root
    popup.grab_set()       # Make it modal

    label = ttk.Label(popup, text="An error occurred:", font=("Arial", 12, "bold"))
    label.pack(pady=(10, 5))

    text_frame = ttk.Frame(popup)
    text_frame.pack(fill="both", expand=True, padx=10, pady=5)

    text_widget = tk.Text(text_frame, wrap="word")
    text_widget.insert("1.0", message)
    text_widget.config(state="normal")  # Allow selection
    text_widget.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
    scrollbar.pack(side="right", fill="y")
    text_widget.config(yscrollcommand=scrollbar.set)

    close_btn = ttk.Button(popup, text="Close", command=popup.destroy)
    close_btn.pack(pady=10)

def install_tk_exception_handler(root):
    """
    Install a global handler for uncaught exceptions raised inside Tkinter
    callbacks (button commands, event bindings, lambdas, ``after`` jobs, etc.).

    Tkinter routes every uncaught callback exception through the root window's
    ``report_callback_exception``. Overriding it here guarantees that *any*
    callback error is shown to the user and logged, even for callbacks that are
    not wrapped with :func:`handle_errors`. This is essential for windowed
    PyInstaller builds, where stderr is not visible and the app would otherwise
    fail silently.

    Args:
        root (tkinter.Tk): The application root window.
    """
    def report_callback_exception(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        popup_message = (
            "An unexpected error occurred:\n\n"
            f"Exception: {exc_value}\n\n"
            f"Traceback:\n{tb}"
        )
        try:
            show_error_popup("Error", popup_message)
        except Exception:
            # Never let the error handler itself crash the app.
            pass
        log_error_to_file("tkinter.callback", (), {}, "Unhandled Tk callback exception", tb)

    root.report_callback_exception = report_callback_exception


def handle_errors(custom_message=None):
    """
    Decorator that catches exceptions, shows a popup, and logs error details.

    Args:
        custom_message (str, optional): Custom message to display and log.

    Returns:
        Callable: Wrapped function with error handling.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                tb = traceback.format_exc()
                function_name = func.__name__

                # Compose popup message
                popup_message = (
                    f"{custom_message or 'An error occurred:'}\n\n"
                    f"Function: {function_name}\n\n"
                    f"Args: {args}\nKwargs: {kwargs}\n\n"
                    f"Traceback:\n{tb}"
                )

                show_error_popup("Error", popup_message)
                log_error_to_file(function_name, args, kwargs, custom_message, tb)
        return wrapper
    return decorator
