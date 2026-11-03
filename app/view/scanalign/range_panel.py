"""
ScanAlign Range Panel.

"Slice Matching" controls: first/last slice per scan (buttons and F / L shortcuts on
the viewers), the number of pairs N, the resulting pair list and a summary line.
Every change updates the link strip (range mode) and notifies change listeners
(the export panel).

Key contents:
- RangePanel: Range rows, N spinbox, pair list; ranges / pairs / n properties.
- add_change_listener: Register a callback fired after every state change.
- on_stack_changed: Clears the range of a scan whose stack was replaced.

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

from pydantic import ValidationError

from app.logic.scanalign.matching_service import build_pairs, max_pairs, range_summary
from app.logic.scanalign.models import SlicePair, SliceRange
from app.view.shared.error_handler import handle_errors
from app.view.shared.tool_tip import Tooltip

DEFAULT_N = 25
_NOT_SET = "not set"
_SHORTCUT_TIP = (
    "Use the slice currently shown in this scan. Shortcut: {key} while hovering the scan."
)


class RangePanel:
    """Controls in the ``scan_range`` frame: slice ranges, N and the pair list."""

    def __init__(self, context, frame_key="scan_range"):
        self.context = context
        self.frame = context.get_frame(frame_key)
        self.viewers = {
            1: context.get_panel("scan_viewer_1"),
            2: context.get_panel("scan_viewer_2"),
        }
        self.link_strip = context.get_panel("scan_link", required=False)

        self._first = {1: None, 2: None}  # 0-based positions, None = not set
        self._last = {1: None, 2: None}
        self._ranges = None
        self._pairs = []
        self._n = None
        self._listeners = []
        self._ranges_sent = None  # last value handed to link_strip.set_ranges
        self._suppress_n_trace = False  # True while _recompute clamps n_var itself

        self._build()
        self._bind_shortcuts()
        self._recompute()

    # ------------------------------------------------------------------ UI

    def _build(self):
        self.frame.columnconfigure(0, weight=1)
        self.range_labels = {}
        self.buttons = {}
        for slot in (1, 2):
            block = ttk.Frame(self.frame)
            block.grid(row=slot - 1, column=0, sticky="ew", padx=6, pady=(6, 0))
            ttk.Label(block, text=f"Scan {slot}", font=("TkDefaultFont", 9, "bold")).grid(
                row=0, column=0, sticky="w"
            )
            first_label = ttk.Label(block, text=f"first: {_NOT_SET}", bootstyle="secondary")
            first_label.grid(row=0, column=1, padx=(10, 0), sticky="w")
            last_label = ttk.Label(block, text=f"last: {_NOT_SET}", bootstyle="secondary")
            last_label.grid(row=0, column=2, padx=(10, 0), sticky="w")
            first_btn = ttk.Button(
                block,
                text="Set first",
                command=lambda s=slot: self.set_first(s),
                bootstyle="secondary-outline",
            )
            first_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0), padx=(0, 3))
            last_btn = ttk.Button(
                block,
                text="Set last",
                command=lambda s=slot: self.set_last(s),
                bootstyle="secondary-outline",
            )
            last_btn.grid(row=1, column=2, sticky="ew", pady=(3, 0))
            Tooltip(first_btn, text=_SHORTCUT_TIP.format(key="F"), wraplength=260)
            Tooltip(last_btn, text=_SHORTCUT_TIP.format(key="L"), wraplength=260)
            self.range_labels[slot] = (first_label, last_label)
            self.buttons[slot] = (first_btn, last_btn)

        self.summary_label = ttk.Label(self.frame, text="")
        self.summary_label.grid(row=2, column=0, sticky="w", padx=6, pady=(8, 0))
        self.warning_label = ttk.Label(
            self.frame, text="", wraplength=260, justify="left", bootstyle="warning"
        )
        self.warning_label.grid(row=3, column=0, sticky="w", padx=6)

        n_row = ttk.Frame(self.frame)
        n_row.grid(row=4, column=0, sticky="w", padx=6, pady=(6, 0))
        ttk.Label(n_row, text="Number of pairs N").pack(side="left")
        self.n_var = tk.StringVar(value=str(DEFAULT_N))
        self.n_spinbox = ttk.Spinbox(n_row, from_=2, to=9999, width=6, textvariable=self.n_var)
        self.n_spinbox.pack(side="left", padx=(6, 0))
        self.n_var.trace_add("write", self._on_n_changed)

        tree_frame = ttk.Frame(self.frame)
        tree_frame.grid(row=5, column=0, sticky="ew", padx=6, pady=(6, 6))
        tree_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_frame, columns=("k", "s1", "s2"), show="headings", height=8, selectmode="browse"
        )
        for col, text, width in (("k", "k", 40), ("s1", "Scan 1", 80), ("s2", "Scan 2", 80)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="e", stretch=col != "k")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _bind_shortcuts(self):
        # add="+": the base canvas panel owns the other bindings (arrows, wheel, ...).
        for slot, viewer in self.viewers.items():
            for key in ("f", "F"):
                viewer.canvas.bind(
                    f"<KeyPress-{key}>", lambda _e, s=slot: self.set_first(s), add="+"
                )
            for key in ("l", "L"):
                viewer.canvas.bind(
                    f"<KeyPress-{key}>", lambda _e, s=slot: self.set_last(s), add="+"
                )

    # ----------------------------------------------------------- public API

    @property
    def ranges(self):
        """``(r1, r2)`` when both ranges are set and valid, else ``None``."""
        return self._ranges

    @property
    def pairs(self):
        """Current ``list[SlicePair]`` (empty when ranges or N are invalid)."""
        return list(self._pairs)

    @property
    def n(self):
        """The entered N, or ``None`` when the field is not a valid integer."""
        return self._n

    def add_change_listener(self, callback):
        """Register ``callback()`` fired after every state change."""
        self._listeners.append(callback)

    @handle_errors("ScanAlign set first")
    def set_first(self, slot):
        index = self.viewers[slot].current_index
        if index is None:
            return
        self._first[slot] = index
        self._recompute()

    @handle_errors("ScanAlign set last")
    def set_last(self, slot):
        index = self.viewers[slot].current_index
        if index is None:
            return
        self._last[slot] = index
        self._recompute()

    @handle_errors("ScanAlign range on_stack_changed")
    def on_stack_changed(self, slot):
        """A new stack was loaded into ``slot``: forget its range."""
        self._first[slot] = None
        self._last[slot] = None
        self._recompute()

    # ---------------------------------------------------------------- state

    def _number(self, slot, index):
        stack = self.viewers[slot].stack
        number = stack.files[index].slice_number if stack else None
        return number if number is not None else index + 1

    def _slot_range(self, slot):
        """Valid ``SliceRange`` for ``slot`` or ``None``."""
        first, last = self._first[slot], self._last[slot]
        if first is None or last is None:
            return None
        try:
            return SliceRange(first=first, last=last)
        except ValidationError:
            return None

    def _parse_n(self):
        try:
            return int(self.n_var.get().strip())
        except ValueError:
            return None

    @handle_errors("ScanAlign N changed")
    def _on_n_changed(self, *_args):
        if not self._suppress_n_trace:
            self._recompute()

    def _recompute(self):
        warnings = []
        for slot in (1, 2):
            first, last = self._first[slot], self._last[slot]
            first_label, last_label = self.range_labels[slot]
            first_label.configure(
                text="first: " + (_NOT_SET if first is None else f"#{self._number(slot, first)}")
            )
            last_label.configure(
                text="last: " + (_NOT_SET if last is None else f"#{self._number(slot, last)}")
            )
            if first is not None and last is not None and first >= last:
                warnings.append(f"Scan {slot}: first slice must come before the last slice")

        r1, r2 = self._slot_range(1), self._slot_range(2)
        ranges = (r1, r2) if r1 is not None and r2 is not None else None
        self._ranges = ranges
        self._n = self._parse_n()

        pairs = []
        if ranges is None:
            self.summary_label.configure(text="")
        else:
            offset, scale = range_summary(*ranges)
            self.summary_label.configure(
                text=f"{r1.length} / {r2.length} slices · offset {offset:+d} · scale {scale:.2f}"
            )
            limit = max_pairs(*ranges)
            self.n_spinbox.configure(to=limit)
            if self._n is not None and self._n > limit:
                # Clamp in place. Tcl suppresses nested traces when this runs inside the
                # n_var write trace, so never rely on the trace re-entering _recompute.
                self._n = limit
                self._suppress_n_trace = True
                try:
                    self.n_var.set(str(limit))
                finally:
                    self._suppress_n_trace = False
            if self._n is None or self._n < 2:
                warnings.append(f"N must be a whole number between 2 and {limit}")
            else:
                pairs = build_pairs(self.viewers[1].stack, self.viewers[2].stack, *ranges, self._n)
        self._pairs = pairs
        self.warning_label.configure(text="\n".join(warnings))
        self._fill_tree(pairs)

        if self.link_strip is not None:
            if ranges != self._ranges_sent:
                self._ranges_sent = ranges
                self.link_strip.set_ranges(*(ranges if ranges is not None else (None, None)))
            self.link_strip.refresh()
        for callback in list(self._listeners):
            callback()

    def _fill_tree(self, pairs: list[SlicePair]):
        self.tree.delete(*self.tree.get_children())
        for pair in pairs:
            self.tree.insert(
                "", "end", iid=str(pair.k - 1), values=(pair.k, pair.slice1, pair.slice2)
            )

    @handle_errors("ScanAlign pair selected")
    def _on_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        pair = self._pairs[int(selection[0])]
        self.viewers[1].show_index(pair.index1, notify=False)
        self.viewers[2].show_index(pair.index2, notify=False)
        if self.link_strip is not None:
            self.link_strip.refresh()
