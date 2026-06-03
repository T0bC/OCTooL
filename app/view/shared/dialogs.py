#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized message-box helpers for the view layer.

These reuse the existing application root via the ``parent`` argument instead of
spawning throwaway ``tk.Tk()`` instances. Pass the panel's root/frame as ``parent``.
If ``parent`` is ``None`` the active default root is used.
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
