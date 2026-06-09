# -*- coding: utf-8 -*-
"""
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
