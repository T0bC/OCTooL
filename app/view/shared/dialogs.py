#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared Dialog Helpers.

Thin, parent-anchored wrappers around tkinter.messagebox for consistent error,
info, and warning dialogs across the application.

Key contents:
- show_error: Parent-anchored error message box.
- show_info: Parent-anchored information message box.
- show_warning: Parent-anchored warning message box.

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


from tkinter import messagebox


def show_error(parent, title: str, message: str) -> None:
    """Display an error message box anchored to ``parent``."""
    messagebox.showerror(title, message, parent=parent)


def show_info(parent, title: str, message: str) -> None:
    """Display an informational message box anchored to ``parent``."""
    messagebox.showinfo(title, message, parent=parent)


def show_warning(parent, title: str, message: str) -> None:
    """Display a warning message box anchored to ``parent``."""
    messagebox.showwarning(title, message, parent=parent)
