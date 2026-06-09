#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application entry point.

Bootstraps the OCTooL GUI and enforces the multiprocessing freeze support
required by PyInstaller-bundled builds. Any unhandled exception during startup
is caught, logged, and presented to the user via a modal error dialog.

Key contents:
- main block: orchestrates freeze_support(), MainGui instantiation, and startup.
- show_error_popup: displays a user-friendly dialog for critical startup errors.
- log_error_to_file: persists the traceback to a daily log file.

Created on Sat Oct 10 19:47:52 2020

@author: Tobias Meissner

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

import sys
import os
import traceback
import tkinter as tk
import multiprocessing
from app.view import MainGui as mainGui
from app.view.shared.error_handler import show_error_popup
from app.logic.shared.logging_utils import log_error_to_file

if __name__ == '__main__':
    # CRITICAL: Required for PyInstaller executables on Windows
    # Prevents worker processes from re-launching the GUI
    multiprocessing.freeze_support()
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
        log_error_to_file("OCTooL.main", (), {}, "Critical startup error", tb)

