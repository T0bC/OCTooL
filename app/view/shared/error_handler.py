# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 10:37:54 2025

@author: Tobias Meissner

Tkinter-dependent error surfacing: popups, the global Tk callback exception
handler, and the ``handle_errors`` decorator. The pure file-logging helper
``log_error_to_file`` lives in ``app.logic.shared.logging_utils`` and is
re-exported here for convenience.
"""

import traceback
import tkinter as tk
from tkinter import ttk

from app.logic.shared.logging_utils import log_error_to_file


def show_error_popup(title, message):
    """
    Displays a custom Tkinter popup window with a scrollable, selectable text area.

    Args:
        title (str): Title of the popup window.
        message (str): Error message and traceback to display.
    """


    root = tk._default_root  # Get the default root window
    if root is None:
        root = tk.Tk()  # Create one if it doesn't exist

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
