"""
ScanAlign Overlay Panel.

Control row in the Scan 2 viewer that switches the viewer between plain Scan 2 and
an overlay of Scan 2 on Scan 1 (alpha blend, checkerboard, difference, magenta/green
fusion). Scan 1 is resampled into Scan 2's grid by physical size, so zoom, pan and
slice navigation of viewer 2 keep working. The resampled Scan 1 is cached, so
scrolling Scan 2 or changing the mode only recombines the images.

Key contents:
- OverlayPanel: Show switch, mode box and per-mode parameter widget; O key toggles.
- on_stack_changed: Clears the cache and updates the enabled state after a load.

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

from app.logic.scanalign.overlay import (
    DEFAULT_ALPHA,
    DEFAULT_TILE,
    compose_arrays,
    resample_to,
)
from app.logic.scanalign.view_geometry import grid_map
from app.view.shared.error_handler import handle_errors
from app.view.shared.tool_tip import Tooltip

_MODES = {
    "Blend": "blend",
    "Checkerboard": "checker",
    "Difference": "difference",
    "Magenta/green": "fusion",
}
_TILE_MIN, _TILE_MAX, _TILE_STEP = 16, 512, 16
_OVERLAY_TITLE = "Scan 2 (moving) · overlay on Scan 1"
_LEGEND = "Scan 1 green · Scan 2 magenta"
_SHORTCUT_TIP = "Show Scan 2 overlaid on Scan 1 (shortcut: O while hovering a scan)."


class OverlayPanel:
    """Overlay controls in viewer 2's frame (grid row 4)."""

    def __init__(self, context, frame_key="scan_viewer_2"):
        self.context = context
        self.frame = context.get_frame(frame_key)
        self.viewer1 = context.get_panel("scan_viewer_1")
        self.viewer2 = context.get_panel("scan_viewer_2")
        self._base_title = self.frame.cget("text")
        self._active = False  # compositor installed on viewer 2
        self._cache = None  # (img1, size, map, array, mask); img1 kept so its id stays unique
        self._refresh_job = None

        self._build()
        self._bind_shortcuts()
        self.viewer1.add_image_listener(self._on_viewer1_image)
        self._update_state()

    # ------------------------------------------------------------------ UI

    def _build(self):
        self.row = ttk.Frame(self.frame)
        self.row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=4, pady=(2, 2))

        ttk.Label(self.row, text="Show:").pack(side="left")
        self.view_var = tk.StringVar(value="scan2")
        self.scan2_radio = ttk.Radiobutton(
            self.row,
            text="Scan 2",
            value="scan2",
            variable=self.view_var,
            command=self._on_view_changed,
            bootstyle="toolbutton",
        )
        self.scan2_radio.pack(side="left", padx=(4, 0))
        self.overlay_radio = ttk.Radiobutton(
            self.row,
            text="Overlay",
            value="overlay",
            variable=self.view_var,
            command=self._on_view_changed,
            bootstyle="toolbutton",
        )
        self.overlay_radio.pack(side="left", padx=(2, 8))
        Tooltip(self.overlay_radio, text=_SHORTCUT_TIP, wraplength=260)

        self.mode_var = tk.StringVar(value="Blend")
        self.mode_box = ttk.Combobox(
            self.row,
            textvariable=self.mode_var,
            values=list(_MODES),
            state="readonly",
            width=14,
        )
        self.mode_box.pack(side="left", padx=(0, 8))
        self.mode_box.bind("<<ComboboxSelected>>", self._on_mode_changed)

        # Parameter area: exactly one of the three groups is shown (none for Difference).
        self.params = ttk.Frame(self.row)
        self.params.pack(side="left")

        self.opacity_group = ttk.Frame(self.params)
        ttk.Label(self.opacity_group, text="Scan 2 opacity").pack(side="left")
        self.opacity_var = tk.DoubleVar(value=DEFAULT_ALPHA * 100)
        self.opacity_scale = ttk.Scale(
            self.opacity_group,
            from_=0,
            to=100,
            length=120,
            variable=self.opacity_var,
            command=self._on_opacity_changed,
        )
        self.opacity_scale.pack(side="left", padx=4)
        self.opacity_label = ttk.Label(self.opacity_group, text=self._opacity_text(), width=5)
        self.opacity_label.pack(side="left")

        self.tile_group = ttk.Frame(self.params)
        ttk.Label(self.tile_group, text="Tile px").pack(side="left")
        self.tile_var = tk.StringVar(value=str(DEFAULT_TILE))
        self.tile_spin = ttk.Spinbox(
            self.tile_group,
            from_=_TILE_MIN,
            to=_TILE_MAX,
            increment=_TILE_STEP,
            width=5,
            textvariable=self.tile_var,
        )
        self.tile_spin.pack(side="left", padx=4)
        self.tile_var.trace_add("write", self._on_tile_changed)

        self.legend_group = ttk.Frame(self.params)
        ttk.Label(self.legend_group, text=_LEGEND, bootstyle="secondary").pack(side="left")

        self.pixels_label = ttk.Label(self.row, text="pixels 1:1 (no µm/px)", bootstyle="warning")
        # Packed on demand in _update_state (right side).

    def _bind_shortcuts(self):
        # add="+": the base canvas panel owns the other bindings (arrows, wheel, ...).
        for viewer in (self.viewer1, self.viewer2):
            for key in ("o", "O"):
                viewer.canvas.bind(f"<KeyPress-{key}>", self._on_shortcut, add="+")

    # --------------------------------------------------------------- helpers

    @property
    def mode(self):
        return _MODES.get(self.mode_var.get(), "blend")

    @property
    def overlay_on(self):
        return self.view_var.get() == "overlay" and self._loaded()

    def _loaded(self):
        return self.viewer1.stack is not None and self.viewer2.stack is not None

    def _opacity_text(self):
        return f"{int(round(self.opacity_var.get()))} %"

    def _alpha(self):
        return min(1.0, max(0.0, float(self.opacity_var.get()) / 100))

    def _tile(self):
        try:
            tile = int(float(self.tile_var.get()))
        except (ValueError, tk.TclError):
            return DEFAULT_TILE
        return min(_TILE_MAX, max(_TILE_MIN, tile))

    def _grid_map(self):
        return grid_map(self.viewer1.stack.geometry, self.viewer2.stack.geometry)

    # --------------------------------------------------------------- actions

    @handle_errors("ScanAlign overlay shortcut")
    def _on_shortcut(self, _event=None):
        if not self._loaded():
            return
        self.view_var.set("scan2" if self.view_var.get() == "overlay" else "overlay")
        self._on_view_changed()

    @handle_errors("ScanAlign overlay view change")
    def _on_view_changed(self):
        self._update_state()

    @handle_errors("ScanAlign overlay mode change")
    def _on_mode_changed(self, _event=None):
        self._show_param_group()
        self._refresh()

    @handle_errors("ScanAlign overlay opacity")
    def _on_opacity_changed(self, _value=None):
        self.opacity_label.configure(text=self._opacity_text())
        if self._refresh_job is None and self.overlay_on and self.mode == "blend":
            self._refresh_job = self.row.after_idle(self._run_refresh_job)

    @handle_errors("ScanAlign overlay refresh job")
    def _run_refresh_job(self):
        self._refresh_job = None
        self._refresh()

    @handle_errors("ScanAlign overlay tile change")
    def _on_tile_changed(self, *_args):
        if self.mode == "checker":
            self._refresh()

    @handle_errors("ScanAlign overlay viewer 1 image")
    def _on_viewer1_image(self, _role):
        self._refresh()

    def _refresh(self):
        if self._active:
            self.viewer2.refresh_composite()

    @handle_errors("ScanAlign overlay on_stack_changed")
    def on_stack_changed(self, slot):
        """A stack was (re)loaded into a viewer: drop the cache, update controls."""
        self._cache = None
        self._update_state()

    # ----------------------------------------------------------------- state

    def _show_param_group(self):
        for group in (self.opacity_group, self.tile_group, self.legend_group):
            group.pack_forget()
        group = {
            "blend": self.opacity_group,
            "checker": self.tile_group,
            "fusion": self.legend_group,
        }.get(self.mode)
        if group is not None:
            group.pack(side="left")

    def _update_state(self):
        loaded = self._loaded()
        if not loaded and self.view_var.get() == "overlay":
            self.view_var.set("scan2")
        on = self.view_var.get() == "overlay" and loaded

        radio_state = "normal" if loaded else "disabled"
        self.scan2_radio.configure(state=radio_state)
        self.overlay_radio.configure(state=radio_state)
        self.mode_box.configure(state="readonly" if on else "disabled")
        inner = "normal" if on else "disabled"
        self.opacity_scale.state(["!disabled"] if on else ["disabled"])
        self.tile_spin.configure(state=inner)
        self._show_param_group()

        if loaded and not self._grid_map().physical:
            self.pixels_label.pack(side="right", padx=(8, 0))
        else:
            self.pixels_label.pack_forget()

        changed = on != self._active
        self._active = on
        if changed:
            self.frame.configure(text=_OVERLAY_TITLE if on else self._base_title)
            self.viewer2.set_compositor(self._compose if on else None)
        elif on:
            self.viewer2.refresh_composite()

    # ------------------------------------------------------------- composing

    def _compose(self, img2):
        """Compositor for viewer 2: Scan 1 (current slice) combined with ``img2``."""
        img1 = self.viewer1.slice_image
        if img1 is None:
            return img2
        m = self._grid_map()
        cache = self._cache
        if cache is not None and cache[0] is img1 and cache[1] == img2.size and cache[2] == m:
            array, mask = cache[3], cache[4]
        else:
            array, mask = resample_to(img1, m, img2.size)
            self._cache = (img1, img2.size, m, array, mask)
        return compose_arrays(array, mask, img2, self.mode, self._alpha(), self._tile())
