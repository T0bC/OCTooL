# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 10:37:54 2025

@author: meissnerto
"""

import traceback
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import os

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

def log_error_to_file(function_name, args, kwargs, custom_message, traceback_text):
    """
    Logs error details to a daily log file in the 'logs/' directory.

    Args:
        function_name (str): Name of the function where the error occurred.
        args (tuple): Positional arguments passed to the function.
        kwargs (dict): Keyword arguments passed to the function.
        custom_message (str): Optional custom error message.
        traceback_text (str): Full traceback string.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Create logs directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_filename = f"error_log_{date_str}.txt"
    log_path = os.path.join(logs_dir, log_filename)

    # Format arguments
    args_str = ", ".join(repr(a) for a in args)
    kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())

    log_entry = (
        f"\n{'='*80}\n"
        f"🕒 Timestamp: {date_str} {time_str}\n"
        f"🔧 Function: {function_name}\n"
        f"📌 Message: {custom_message or 'Unhandled exception'}\n"
        f"🧩 Args: {args_str}\n"
        f"🧩 Kwargs: {kwargs_str}\n"
        f"{'-'*80}\n"
        f"{traceback_text}\n"
        f"{'='*80}\n"
    )

    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

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


