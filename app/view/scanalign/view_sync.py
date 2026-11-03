"""
ScanAlign View Sync.

Keeps the zoom/pan of the two scan viewers on the same physical region. A view
change in one viewer is mapped through the grid map (physical size, centred) and
applied to the other. Without pixel sizes, pixels are matched 1:1. Works against
a small viewer protocol (stack, view_state, apply_view, add_view_listener) and has
no tkinter dependency.

Key contents:
- ViewSync: Mirrors zoom/pan between two viewers; set_enabled, physical.

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

from app.logic.scanalign.view_geometry import grid_map, map_view

# zoom_level == 1.0 is the base viewer's "fit" sentinel; a mapped zoom of exactly 1.0
# must not be mistaken for it.
_NOT_FIT = 1.0 + 1e-6


class ViewSync:
    """Mirror zoom/pan between viewer 1 (Scan 1) and viewer 2 (Scan 2)."""

    def __init__(self, viewer1, viewer2):
        self.viewer1 = viewer1
        self.viewer2 = viewer2
        self.enabled = True
        self._busy = False
        viewer1.add_view_listener(self._on_view_changed)
        viewer2.add_view_listener(self._on_view_changed)

    def _both_loaded(self):
        return self.viewer1.stack is not None and self.viewer2.stack is not None

    @property
    def physical(self):
        """True if the views are matched by physical size (or nothing is loaded yet)."""
        if not self._both_loaded():
            return True
        return grid_map(self.viewer1.stack.geometry, self.viewer2.stack.geometry).physical

    def set_enabled(self, enabled):
        """Switch syncing on/off; turning it on aligns viewer 2 to viewer 1."""
        self.enabled = bool(enabled)
        if self.enabled:
            self._sync(self.viewer1, self.viewer2)

    def _on_view_changed(self, role):
        if not self.enabled:
            return
        if role == 1:
            self._sync(self.viewer1, self.viewer2)
        else:
            self._sync(self.viewer2, self.viewer1)

    def _sync(self, source, target):
        if self._busy or not self._both_loaded():
            return
        state = source.view_state()
        if state is None:
            return
        zoom, ox, oy, is_fit, src_canvas = state
        self._busy = True
        try:
            if is_fit:
                target.apply_view(1.0, 0, 0)
                return
            target_state = target.view_state()
            if target_state is None:
                return
            m = grid_map(self.viewer1.stack.geometry, self.viewer2.stack.geometry)
            new_zoom, nx, ny = map_view(
                zoom, ox, oy, src_canvas, target_state[4], m, source is self.viewer1
            )
            if new_zoom == 1.0:
                new_zoom = _NOT_FIT
            target.apply_view(new_zoom, nx, ny)
        finally:
            self._busy = False
