#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 19:47:52 2020

@author: Tobias Meissner
"""
import traceback
import tkinter as tk
import MainGui as mainGui
from utils.error_handler import show_error_popup, log_error_to_file

try:
    myWindow = mainGui.MainGui()
    myWindow.start()
except Exception as e:
    # Use centralized error handler for consistent UX and logging
    tb = traceback.format_exc()
    error_message = (
        f"Critical error during application startup:\n\n"
        f"Exception: {str(e)}\n\n"
        f"Traceback:\n{tb}"
    )
    
    # Ensure we have a Tk root for the error popup
    if tk._default_root is None:
        root = tk.Tk()
        root.withdraw()
    
    show_error_popup("Application Startup Error", error_message)
    log_error_to_file("OCTexVIEW.main", (), {}, "Critical startup error", tb)

