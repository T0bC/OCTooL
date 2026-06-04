# -*- coding: utf-8 -*-
"""
Metadata Prompt Utility

Provides a reusable dialog for prompting users to enter operator and measurement metadata.

Created on Wed Oct 09 2025
@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk


def prompt_for_metadata(parent_window, context, callback=None, title="Enter Analysis Metadata"):
    """
    Show a modal dialog to prompt for operator and measurement metadata.
    
    Args:
        parent_window: Parent Tk window
        context: Application context to store metadata
        callback: Optional callback function to call after metadata is set
        title: Dialog title
    
    Returns:
        The popup window (for testing purposes)
    """
    popup = tk.Toplevel(parent_window)
    
    # Set position of the popup to the center of the main UI
    popup.update_idletasks()
    
    main_x = parent_window.winfo_x()
    main_y = parent_window.winfo_y()
    main_width = parent_window.winfo_width()
    main_height = parent_window.winfo_height()
    
    popup_width = popup.winfo_width()
    popup_height = popup.winfo_height()
    
    pos_x = main_x + (main_width // 2) - (popup_width // 2)
    pos_y = main_y + (main_height // 2) - (popup_height // 2)
    
    popup.geometry(f"+{pos_x}+{pos_y}")
    
    popup.title(title)
    popup.transient(parent_window)
    popup.grab_set()
    
    # Get current metadata if available
    metadata = getattr(context, "analysis_metadata", {})
    current_operator = metadata.get("operator", "")
    current_measurement = metadata.get("measurement", "")
    
    tk.Label(popup, text="Operator Initials:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
    operator_var = tk.StringVar(value=current_operator)
    operator_entry = tk.Entry(popup, textvariable=operator_var)
    operator_entry.grid(row=0, column=1, padx=10, pady=5)
    operator_entry.focus_set()
    
    tk.Label(popup, text="Measurement Number:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
    measurement_var = tk.StringVar(value=str(current_measurement) if current_measurement else "")
    measurement_entry = tk.Entry(popup, textvariable=measurement_var)
    measurement_entry.grid(row=1, column=1, padx=10, pady=5)
    
    def submit():
        operator = operator_var.get().strip()
        if not operator:
            if hasattr(context, 'status_bar') and context.status_bar:
                context.status_bar.update("Operator initials cannot be empty.", level="warning")
            return
        
        try:
            measurement = int(measurement_var.get())
        except ValueError:
            if hasattr(context, 'status_bar') and context.status_bar:
                context.status_bar.update("Measurement must be an integer.", level="warning")
            return
        
        # Store metadata in context
        context.analysis_metadata = {
            "operator": operator,
            "measurement": measurement
        }
        
        popup.destroy()
        
        # Call callback if provided
        if callback:
            callback()
    
    def on_enter(event):
        submit()
    
    # Bind Enter key to submit
    operator_entry.bind("<Return>", on_enter)
    measurement_entry.bind("<Return>", on_enter)
    
    ttk.Button(popup, text="Submit", command=submit).grid(row=2, column=0, columnspan=2, pady=10)
    
    return popup


def get_metadata_from_context(context):
    """
    Get operator and measurement from context.
    
    Args:
        context: Application context
    
    Returns:
        tuple: (operator, measurement) or (None, None) if not set
    """
    metadata = getattr(context, "analysis_metadata", {})
    operator = metadata.get("operator", "").strip()
    measurement = metadata.get("measurement", None)
    
    if not operator or measurement is None:
        return None, None
    
    return operator, measurement


def ensure_metadata_set(parent_window, context, callback):
    """
    Ensure metadata is set, prompting user if necessary.
    
    Args:
        parent_window: Parent Tk window
        context: Application context
        callback: Function to call after metadata is confirmed/set
    
    Returns:
        bool: True if metadata is already set, False if prompt was shown
    """
    operator, measurement = get_metadata_from_context(context)
    
    if operator and measurement is not None:
        # Metadata already set, call callback immediately
        callback()
        return True
    else:
        # Prompt for metadata, callback will be called after
        prompt_for_metadata(parent_window, context, callback, 
                          title="Metadata Required")
        return False
