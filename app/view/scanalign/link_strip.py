"""
ScanAlign Link Strip.

Thin strip between the two scan viewers with the link toggle and the slice
offset (delta). With the link off, delta shows the live difference between the
two viewer positions; with the link on, delta is frozen and a user-driven change
in one viewer moves the other by the same offset. With both slice ranges set
(see the range panel) the link switches to range mode and maps positions
linearly between the ranges instead; a pair marker shows when both viewers sit
on a matched pair.

Key contents:
- LinkStrip: Link toggle, delta label and slice-number label; drives linked stepping.
- on_stack_changed: Resets the link when a new stack is loaded.
- set_ranges: Switches range mode on/off; refresh: Redraws the labels.

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

from app.logic.scanalign.matching_service import (
    compute_offset,
    linked_index,
    range_linked_index,
    range_summary,
)
from app.view.shared.error_handler import handle_errors
from app.view.shared.tool_tip import Tooltip

_DELTA_TIP = (
    "Delta is the slice offset between the scans: position in Scan 2 minus position in "
    "Scan 1. With Link on, it stays fixed and scrolling one scan moves the other by "
    "the same amount. With Link off it follows the current positions."
)


class LinkStrip:
    """Link toggle + delta display living in the ``scan_link`` frame."""

    def __init__(self, context, frame_key="scan_link"):
        self.context = context
        self.frame = context.get_frame(frame_key)
        self.viewer1 = context.get_panel("scan_viewer_1")
        self.viewer2 = context.get_panel("scan_viewer_2")
        self.linked = False
        self.offset = 0
        self._out_of_range = False
        self._ranges = None  # (r1, r2) when range mode is active

        self.link_var = tk.BooleanVar(value=False)
        self.check = ttk.Checkbutton(
            self.frame,
            text="Link scans",
            variable=self.link_var,
            command=self._on_toggle,
            bootstyle="round-toggle",
        )
        self.check.grid(row=0, column=0, padx=(8, 12), pady=2)

        self.delta_label = ttk.Label(self.frame, text="", bootstyle="secondary")
        self.delta_label.grid(row=0, column=1, padx=(0, 12))

        self.pair_label = ttk.Label(self.frame, text="", bootstyle="secondary")
        self.pair_label.grid(row=0, column=2, padx=(0, 8))

        Tooltip(self.check, text=_DELTA_TIP, wraplength=280)
        Tooltip(self.delta_label, text=_DELTA_TIP, wraplength=280)

        self.viewer1.add_index_listener(self._on_viewer_changed)
        self.viewer2.add_index_listener(self._on_viewer_changed)
        self._refresh()

    # ----------------------------------------------------------------- state

    def _both_loaded(self):
        return self.viewer1.current_index is not None and self.viewer2.current_index is not None

    @handle_errors("ScanAlign link strip on_stack_changed")
    def on_stack_changed(self):
        """A new stack was loaded into a viewer: switch the link off and refresh."""
        self.linked = False
        self.link_var.set(False)
        self._out_of_range = False
        self._refresh()

    @handle_errors("ScanAlign link toggle")
    def _on_toggle(self):
        if not self._both_loaded():
            self.link_var.set(False)
            self.linked = False
        else:
            self.linked = bool(self.link_var.get())
            if self.linked:
                self.offset = compute_offset(self.viewer1.current_index, self.viewer2.current_index)
                self._sync_viewer2_to_ranges()
        self._out_of_range = False
        self._refresh()

    @handle_errors("ScanAlign link strip set_ranges")
    def set_ranges(self, r1, r2):
        """Enter range mode with both ranges, or leave it (``None, None``).

        While linked, viewer 2 jumps to the position mapped from viewer 1.
        """
        self._ranges = (r1, r2) if r1 is not None and r2 is not None else None
        if self.linked and self._both_loaded():
            if self._ranges is not None:
                self._sync_viewer2_to_ranges()
            else:  # keep the current relative position as the frozen offset
                self.offset = compute_offset(self.viewer1.current_index, self.viewer2.current_index)
        self._out_of_range = False
        self._refresh()

    def refresh(self):
        """Redraw the labels (e.g. after the range panel changed the pairs)."""
        self._refresh()

    def _sync_viewer2_to_ranges(self):
        """In range mode, move viewer 2 to the position mapped from viewer 1."""
        if self._ranges is None:
            return
        target, in_range = range_linked_index(
            self.viewer1.current_index, self._ranges[0], self._ranges[1], self.viewer2.slice_count
        )
        self._out_of_range = not in_range
        if target != self.viewer2.current_index:
            self.viewer2.show_index(target)

    @handle_errors("ScanAlign link strip viewer change")
    def _on_viewer_changed(self, role, index, user_initiated):
        if self.linked and user_initiated and self._both_loaded():
            source_is_scan1 = role == 1
            other = self.viewer2 if source_is_scan1 else self.viewer1
            if self._ranges is not None:
                src, tgt = self._ranges if source_is_scan1 else self._ranges[::-1]
                target, in_range = range_linked_index(index, src, tgt, other.slice_count)
            else:
                target, in_range = linked_index(
                    index, self.offset, other.slice_count, source_is_scan1
                )
            self._out_of_range = not in_range
            if target != other.current_index:
                other.show_index(target)
        elif not self.linked:
            self._out_of_range = False
        self._refresh()

    # --------------------------------------------------------------- display

    def _refresh(self):
        ready = self._both_loaded()
        self.check.configure(state="normal" if ready else "disabled")
        if not ready:
            self.delta_label.configure(text="Load both scans to compare", bootstyle="secondary")
            self.pair_label.configure(text="")
            return

        i1, i2 = self.viewer1.current_index, self.viewer2.current_index
        style = "default" if self.linked else "secondary"
        if self.linked and self._ranges is not None:
            offset, scale = range_summary(*self._ranges)
            if abs(scale - 1.0) < 0.005:
                label = f"Δ = {offset:+d} (ranges)"
            else:
                label = f"Linked by ranges · scale {scale:.2f}"
            self.delta_label.configure(text=label, bootstyle=style)
        else:
            delta = self.offset if self.linked else compute_offset(i1, i2)
            self.delta_label.configure(text=f"Δ = {delta:+d} slices", bootstyle=style)
        text = f"#{self._number(self.viewer1, i1)} ↔ #{self._number(self.viewer2, i2)}"
        pair = self._pair_at(i1, i2)
        if pair is not None:
            text += f" · pair k={pair.k}"
        if self._out_of_range:
            self.pair_label.configure(text=text + "  (end of scan)", bootstyle="warning")
        else:
            self.pair_label.configure(text=text, bootstyle="default")

    def _pair_at(self, i1, i2):
        """The matched pair both viewers currently sit on (from the range panel), or None."""
        panel = self.context.get_panel("scan_range", required=False)
        if panel is None:
            return None
        return next((p for p in panel.pairs if p.index1 == i1 and p.index2 == i2), None)

    @staticmethod
    def _number(viewer, index):
        number = viewer.stack.files[index].slice_number
        return number if number is not None else index + 1
