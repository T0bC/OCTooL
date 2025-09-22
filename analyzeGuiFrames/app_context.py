# -*- coding: utf-8 -*-
"""
Created on Thu Sep 11 12:16:39 2025

@author: Tobias Meissner
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
