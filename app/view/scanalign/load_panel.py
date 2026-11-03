"""
ScanAlign Load Panel.

Loads two exported scan folders (reference and moving) in the background, builds
their slice caches, shows the viewers and presents a two-column geometry table
with the comparison verdict and per-scan warnings.

Key contents:
- LoadPanel: Load buttons, per-scan preview progress, geometry table, shutdown hook.
- _on_loaded: Closes the old cache, builds the new one and starts the preview load.
- _refresh_table: Fills the geometry table and highlights differing cells.

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

import contextlib
import threading
import time
import tkinter as tk
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, ttk

from app.logic.scanalign import stack_service
from app.logic.scanalign.slice_cache import (
    SliceCache,
    choose_preview_factor,
    preview_budget_bytes,
)
from app.logic.shared.concurrency import detect_available_memory_gb
from app.view.shared.error_handler import handle_errors, show_error_popup
from app.view.shared.tool_tip import Tooltip

_MISSING = "—"
_PROGRESS_INTERVAL_S = 0.1  # at most 10 UI updates per second

# (label, geometry attribute / formatter key, key in GeometryComparison.differs)
_ROWS = (
    ("Specimen", "specimen", None),
    ("Slices", "n_slices", "n_slices"),
    ("Image W×H px", "size", "size"),
    ("Pixel X µm", "px_size_x_um", "px_size_x_um"),
    ("Pixel Z µm", "px_size_z_um", "px_size_z_um"),
    ("Slice spacing µm", "slice_spacing_um", "slice_spacing_um"),
    ("Length Y mm", "length_y_mm", "length_y_mm"),
    ("Source", "source", None),
)


class LoadPanel:
    """Controls in the ``scan_load`` frame for loading and comparing two scans."""

    def __init__(self, context, frame_key="scan_load"):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame(frame_key)
        self.viewers = {
            1: context.get_panel("scan_viewer_1"),
            2: context.get_panel("scan_viewer_2"),
        }
        self.link_strip = context.get_panel("scan_link", required=False)
        self.range_panel = context.get_panel("scan_range", required=False)
        self.overlay_panel = context.get_panel("scan_overlay", required=False)

        self.stacks = {1: None, 2: None}
        self.caches = {1: None, 2: None}
        self._load_token = {1: 0, 2: 0}
        self._last_dir = None
        self._progress_lock = threading.Lock()
        self._last_ui_push = {1: 0.0, 2: 0.0}
        self._closed = False

        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-load")
        context.register_executor(self._executor)
        context.register_shutdown_hook(self.close)

        self._build()

    # ------------------------------------------------------------------ UI

    def _build(self):
        self.frame.columnconfigure(0, weight=1)
        self.buttons = {}
        self.progress_bars = {}
        self.progress_labels = {}
        titles = {1: "Load Scan 1 (reference)…", 2: "Load Scan 2 (moving)…"}
        for slot in (1, 2):
            block = ttk.Frame(self.frame)
            block.grid(row=slot - 1, column=0, sticky="ew", padx=6, pady=(6, 0))
            block.columnconfigure(0, weight=1)
            button = ttk.Button(
                block,
                text=titles[slot],
                command=lambda s=slot: self.choose_folder(s),
                bootstyle="primary",
            )
            button.grid(row=0, column=0, columnspan=2, sticky="ew")
            bar = ttk.Progressbar(block, mode="determinate", maximum=100, length=120)
            bar.grid(row=1, column=0, sticky="ew", pady=(3, 0))
            label = ttk.Label(block, text="", bootstyle="secondary", width=16)
            label.grid(row=1, column=1, padx=(6, 0), pady=(3, 0))
            self.buttons[slot] = button
            self.progress_bars[slot] = bar
            self.progress_labels[slot] = label

        table = ttk.Frame(self.frame)
        table.grid(row=2, column=0, sticky="ew", padx=6, pady=(8, 0))
        self.table_frame = table
        for col, text in enumerate(("", "Scan 1", "Scan 2")):
            ttk.Label(table, text=text, font=("TkDefaultFont", 9, "bold")).grid(
                row=0, column=col, padx=4, sticky="w"
            )
        self.cells = {}
        self.source_tips = {}
        for r, (label, key, _diff) in enumerate(_ROWS, start=1):
            ttk.Label(table, text=label).grid(row=r, column=0, padx=4, sticky="w")
            for slot in (1, 2):
                cell = ttk.Label(table, text=_MISSING)
                cell.grid(row=r, column=slot, padx=4, sticky="w")
                self.cells[(key, slot)] = cell
                if key == "source":
                    self.source_tips[slot] = Tooltip(cell, text="No scan loaded", wraplength=260)

        self.verdict_label = ttk.Label(self.frame, text="", wraplength=260, justify="left")
        self.verdict_label.grid(row=3, column=0, sticky="w", padx=6, pady=(6, 0))
        self.warning_frame = ttk.Frame(self.frame)
        self.warning_frame.grid(row=4, column=0, sticky="w", padx=6, pady=(2, 6))

    # ------------------------------------------------------------ threading

    def _post(self, func, *args):
        """Run ``func`` on the Tk thread (safe from any thread, ignores a closed UI)."""
        with contextlib.suppress(RuntimeError, tk.TclError):
            self.root.after(0, func, *args)

    # -------------------------------------------------------------- loading

    @handle_errors("ScanAlign choose folder")
    def choose_folder(self, slot):
        folder = filedialog.askdirectory(
            title=f"Select exported scan folder for Scan {slot}",
            initialdir=self._last_dir or None,
            parent=self.frame.winfo_toplevel(),
        )
        if folder:
            self.load_folder(slot, folder)

    def load_folder(self, slot, folder):
        """Load ``folder`` into ``slot`` (1 or 2) in the background."""
        folder = Path(folder)
        self._last_dir = str(folder.parent)
        self._load_token[slot] += 1
        token = self._load_token[slot]
        self.buttons[slot].configure(state="disabled")
        self.progress_bars[slot]["value"] = 0
        self.progress_labels[slot].configure(text="Reading folder…")
        with contextlib.suppress(RuntimeError):  # executor shut down
            self._executor.submit(self._load_worker, slot, folder, token)

    def _load_worker(self, slot, folder, token):
        """Worker thread: read the folder, then hand the result to the Tk thread."""
        try:
            stack = stack_service.load_stack(folder)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            self._post(self._on_load_failed, slot, token, folder, exc, traceback.format_exc())
            return
        self._post(self._on_loaded, slot, token, stack)

    @handle_errors("ScanAlign load failed")
    def _on_load_failed(self, slot, token, folder, exc, tb):
        if token != self._load_token[slot]:
            return
        self.buttons[slot].configure(state="normal")
        self.progress_labels[slot].configure(text="")
        if isinstance(exc, ValueError):
            message = str(exc)
        else:
            message = f"Could not load {folder}:\n{exc}\n\n{tb}"
        show_error_popup(f"Load Scan {slot} failed", message)

    @handle_errors("ScanAlign loaded")
    def _on_loaded(self, slot, token, stack):
        if self._closed or token != self._load_token[slot]:
            return
        self.buttons[slot].configure(state="normal")
        old = self.caches[slot]
        if old is not None:
            old.close()

        geo = stack.geometry
        n = len(stack.files)
        factor = choose_preview_factor(
            n,
            geo.width_px,
            geo.height_px,
            preview_budget_bytes(detect_available_memory_gb()),
        )
        cache = SliceCache(
            [f.path for f in stack.files], (geo.width_px, geo.height_px), preview_factor=factor
        )
        self.stacks[slot] = stack
        self.caches[slot] = cache
        self.progress_bars[slot]["value"] = 0
        self.progress_labels[slot].configure(text="Preview 0 %")

        self.viewers[slot].set_stack(stack, cache)
        if self.link_strip is not None:
            self.link_strip.on_stack_changed()
        if self.range_panel is not None:
            self.range_panel.on_stack_changed(slot)
        if self.overlay_panel is not None:
            self.overlay_panel.on_stack_changed(slot)

        cache.start_preview(
            lambda done, total, s=slot, c=cache: self._on_preview_progress(s, c, done, total),
            lambda cancelled, s=slot, c=cache: self._post(self._on_preview_done, s, c, cancelled),
        )
        self._refresh_table()
        self.context.safe_status_update(
            f"Scan {slot} loaded: {n} slices ({stack.specimen})", level="success"
        )

    # ------------------------------------------------------------- progress

    def _on_preview_progress(self, slot, cache, done, total):
        """Worker thread: push to the UI at most 10x per second."""
        with self._progress_lock:
            now = time.monotonic()
            if now - self._last_ui_push[slot] < _PROGRESS_INTERVAL_S:
                return
            self._last_ui_push[slot] = now
        self._post(self._update_progress, slot, cache, done, total)

    def _update_progress(self, slot, cache, done, total):
        if cache is not self.caches[slot] or not total:
            return
        percent = 100.0 * done / total
        self.progress_bars[slot]["value"] = percent
        self.progress_labels[slot].configure(text=f"Preview {percent:.0f} %")

    def _on_preview_done(self, slot, cache, cancelled):
        if cache is not self.caches[slot] or cancelled:
            return
        self.progress_bars[slot]["value"] = 100
        self.progress_labels[slot].configure(text="Preview ready")

    # ---------------------------------------------------------------- table

    @staticmethod
    def _format(key, stack):
        geo = stack.geometry
        if key == "specimen":
            return stack.specimen or _MISSING
        if key == "n_slices":
            return str(len(stack.files))
        if key == "size":
            return f"{geo.width_px}×{geo.height_px}"
        if key == "source":
            return {"header": "Header.xml", "dpi": "Image DPI"}.get(geo.source, "unknown")
        value = getattr(geo, key, None)
        if value is None:
            return _MISSING
        return f"{value:.2f}"

    @staticmethod
    def _source_tip(stack):
        geo = stack.geometry
        if geo.source == "header":
            name = geo.oct_path.name if geo.oct_path else ".oct file"
            return f"Header.xml of {name}"
        if geo.source == "dpi":
            return "image DPI (no .oct found)"
        return "No physical dimensions available"

    def _refresh_table(self):
        s1, s2 = self.stacks[1], self.stacks[2]
        comparison = None
        if s1 is not None and s2 is not None:
            comparison = stack_service.compare_geometry(s1.geometry, s2.geometry)
        differs = comparison.differs if comparison else {}

        for _label, key, diff_key in _ROWS:
            for slot, stack in ((1, s1), (2, s2)):
                cell = self.cells[(key, slot)]
                if stack is None:
                    cell.configure(text=_MISSING, bootstyle="default")
                    continue
                text = self._format(key, stack)
                if diff_key and differs.get(diff_key):
                    cell.configure(text=f"▲ {text}", bootstyle="warning")
                else:
                    cell.configure(text=text, bootstyle="default")
        for slot, stack in ((1, s1), (2, s2)):
            if stack is not None:
                self.source_tips[slot].text = self._source_tip(stack)

        self.verdict_label.configure(text=comparison.verdict if comparison else "")

        for child in self.warning_frame.winfo_children():
            child.destroy()
        for slot, stack in ((1, s1), (2, s2)):
            if stack is None:
                continue
            for warning in stack.warnings:
                ttk.Label(
                    self.warning_frame,
                    text=f"⚠ Scan {slot}: {warning}",
                    wraplength=260,
                    justify="left",
                    bootstyle="warning",
                ).pack(anchor="w")

    # ------------------------------------------------------------- shutdown

    def close(self):
        """Close both slice caches (shutdown hook; safe to call repeatedly)."""
        self._closed = True
        for slot in (1, 2):
            cache = self.caches[slot]
            if cache is not None:
                with contextlib.suppress(Exception):
                    cache.close()
