# -*- coding: utf-8 -*-
"""
Created on Thu Sep 11 12:16:39 2025

@author: Tobias Meissner
"""
import sys
import os

def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    
    When running as a PyInstaller bundle, files are in sys._MEIPASS.
    When running as a normal script, files are relative to the script location.
    
    Args:
        relative_path: Path relative to the application root (e.g., 'icons/thumb_4.ico')
    
    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Running as normal Python script
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(base_path, relative_path)

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

