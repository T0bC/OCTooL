"""
ScanAlign overlay panel tests.

Exercise the OverlayPanel state logic with a real Tk root (skipped when no display
is available) and lightweight fake viewers.

Key contents:
- TestOverlayPanel: Enabled state, toggling, mode widgets, refresh, shortcut, caching.

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

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest
import ttkbootstrap  # noqa: F401 - patches ttk widgets with bootstyle support
from PIL import Image

from app.logic.scanalign.models import ScanGeometry
from app.view.scanalign import overlay_panel as overlay_panel_module
from app.view.scanalign.overlay_panel import OverlayPanel


def make_stack(px=1.0):
    geometry = ScanGeometry(n_slices=3, width_px=16, height_px=16, px_size_x_um=px, px_size_z_um=px)
    return SimpleNamespace(geometry=geometry)


class FakeViewer:
    def __init__(self, parent, role, title):
        self.role = role
        self.stack = None
        self.slice_image = None
        self.frame = ttk.LabelFrame(parent, text=title)
        self.canvas = tk.Canvas(self.frame)
        self.compositor = None
        self.refresh_count = 0
        self.image_listeners = []

    def add_image_listener(self, callback):
        self.image_listeners.append(callback)

    def set_compositor(self, compositor):
        self.compositor = compositor
        self.refresh_count += 1

    def refresh_composite(self):
        self.refresh_count += 1

    def load(self, px=1.0):
        self.stack = make_stack(px)
        self.slice_image = Image.new("L", (16, 16), 100)

    def change_image(self):
        self.slice_image = Image.new("L", (16, 16), 50)
        for callback in self.image_listeners:
            callback(self.role)


class FakeContext:
    def __init__(self, v1, v2):
        self.frames = {"scan_viewer_2": v2.frame}
        self.panels = {"scan_viewer_1": v1, "scan_viewer_2": v2}

    def get_frame(self, name):
        return self.frames[name]

    def get_panel(self, name, required=True):
        return self.panels.get(name)


@pytest.fixture
def setup(tk_root):
    v1 = FakeViewer(tk_root, 1, "Scan 1 (reference)")
    v2 = FakeViewer(tk_root, 2, "Scan 2 (moving)")
    panel = OverlayPanel(FakeContext(v1, v2), "scan_viewer_2")
    yield v1, v2, panel
    v1.frame.destroy()
    v2.frame.destroy()


def load_both(v1, v2, panel, px=1.0):
    v1.load(px)
    v2.load(px)
    panel.on_stack_changed(1)
    panel.on_stack_changed(2)


class TestOverlayPanel:
    """Tests for OverlayPanel."""

    @pytest.mark.unit
    def test_disabled_until_both_loaded(self, setup):
        """GIVEN one scan loaded, WHEN updating, THEN controls are disabled and shortcut ignored."""
        v1, v2, panel = setup
        v1.load()
        panel.on_stack_changed(1)
        assert str(panel.overlay_radio.cget("state")) == "disabled"
        panel._on_shortcut()
        assert panel.view_var.get() == "scan2"
        assert v2.compositor is None

    @pytest.mark.unit
    def test_toggle_sets_and_clears_compositor(self, setup):
        """GIVEN both loaded, WHEN toggling overlay, THEN compositor and frame title follow."""
        v1, v2, panel = setup
        load_both(v1, v2, panel)
        panel.view_var.set("overlay")
        panel._on_view_changed()
        assert v2.compositor is not None
        assert v2.frame.cget("text") == "Scan 2 (moving) · overlay on Scan 1"
        panel.view_var.set("scan2")
        panel._on_view_changed()
        assert v2.compositor is None
        assert v2.frame.cget("text") == "Scan 2 (moving)"

    @pytest.mark.unit
    def test_mode_change_swaps_parameter_widget_and_refreshes(self, setup):
        """GIVEN overlay on, WHEN the mode changes, THEN one group shows and viewer refreshes."""
        v1, v2, panel = setup
        load_both(v1, v2, panel)
        panel.view_var.set("overlay")
        panel._on_view_changed()
        groups = (panel.opacity_group, panel.tile_group, panel.legend_group)

        def shown():
            return [g for g in groups if g.winfo_manager()]

        assert shown() == [panel.opacity_group]
        before = v2.refresh_count
        for name, expected in (
            ("Checkerboard", [panel.tile_group]),
            ("Difference", []),
            ("Magenta/green", [panel.legend_group]),
            ("Blend", [panel.opacity_group]),
        ):
            panel.mode_var.set(name)
            panel._on_mode_changed()
            assert shown() == expected
        assert v2.refresh_count == before + 4

    @pytest.mark.unit
    def test_viewer1_image_change_refreshes_only_while_on(self, setup):
        """GIVEN viewer 1 changes its image, WHEN overlay is off/on, THEN refresh only when on."""
        v1, v2, panel = setup
        load_both(v1, v2, panel)
        before = v2.refresh_count
        v1.change_image()
        assert v2.refresh_count == before
        panel.view_var.set("overlay")
        panel._on_view_changed()
        before = v2.refresh_count
        v1.change_image()
        assert v2.refresh_count == before + 1

    @pytest.mark.unit
    def test_o_key_toggles_overlay(self, setup):
        """GIVEN both loaded, WHEN O is pressed on a canvas, THEN overlay toggles."""
        v1, v2, panel = setup
        load_both(v1, v2, panel)
        # Key events are not delivered to a withdrawn root, so check the bindings and
        # call the handler they point to.
        for viewer in (v1, v2):
            assert viewer.canvas.bind("<KeyPress-o>")
            assert viewer.canvas.bind("<KeyPress-O>")
        panel._on_shortcut()
        assert panel.view_var.get() == "overlay"
        assert v2.compositor is not None
        panel._on_shortcut()
        assert panel.view_var.get() == "scan2"

    @pytest.mark.unit
    def test_compose_size_and_resample_cache(self, setup, monkeypatch):
        """GIVEN the same Scan 1 image, WHEN composing twice, THEN resample runs once."""
        v1, v2, panel = setup
        load_both(v1, v2, panel)
        calls = []
        real = overlay_panel_module.resample_to
        monkeypatch.setattr(
            overlay_panel_module,
            "resample_to",
            lambda *a: calls.append(1) or real(*a),
        )
        img2 = Image.new("L", (16, 16), 200)
        out = panel._compose(img2)
        panel.mode_var.set("Difference")
        out2 = panel._compose(img2)
        assert out.size == out2.size == img2.size
        assert len(calls) == 1
        v1.change_image()
        panel._compose(img2)
        assert len(calls) == 2

    @pytest.mark.unit
    def test_stack_removed_returns_to_scan2_view(self, setup):
        """GIVEN overlay on, WHEN a scan disappears, THEN the view returns to Scan 2."""
        v1, v2, panel = setup
        load_both(v1, v2, panel)
        panel.view_var.set("overlay")
        panel._on_view_changed()
        v1.stack = None
        panel.on_stack_changed(1)
        assert panel.view_var.get() == "scan2"
        assert v2.compositor is None

    @pytest.mark.unit
    def test_pixels_note_when_no_spacing(self, setup):
        """GIVEN scans without pixel size, WHEN loaded, THEN the pixels 1:1 note is shown."""
        v1, v2, panel = setup
        load_both(v1, v2, panel, px=None)
        assert panel.pixels_label.winfo_manager()
        load_both(v1, v2, panel, px=1.0)
        assert not panel.pixels_label.winfo_manager()
