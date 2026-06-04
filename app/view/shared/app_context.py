# -*- coding: utf-8 -*-
"""
Created on Thu Sep 11 12:16:39 2025

@author: Tobias Meissner

AppContext is the UI coordination hub: it holds references to the root window,
panels, frames, and the status bar, and provides thread-safe status updates.
It lives in the view layer because it coordinates tkinter widgets.
"""


class AppContext:
    def __init__(self):
        self.root = None
        self.panels = {}
        self.frames = {}
        self.config_manager = None

    def register_panel(self, name: str, panel):
        self.panels[name] = panel

    def get_panel(self, name: str, required=True):
        panel = self.panels.get(name)
        if required and panel is None:
            raise ValueError(f"Panel '{name}' not found in context.")
        return panel

    def register_frame(self, name: str, frame):
        self.frames[name] = frame

    def get_frame(self, name: str):
        return self.frames.get(name)

    def safe_status_update(self, message: str, level: str = "info", duration: int = 2000):
        if getattr(self, "status_bar", None) is None:
            return

        target = self.status_bar
        widget = getattr(target, "frame", None) or getattr(target, "label", None)
        if widget is None:
            target.update(message, level, duration)
            return

        widget.after(0, lambda: target.update(message, level, duration))
