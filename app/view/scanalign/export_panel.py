"""
ScanAlign Export Panel.

Exports the matched slice pairs of both scans into two new folders in the
background: target-folder preview, Export / Cancel buttons, determinate progress
and a result summary. The inputs are snapshotted when Export is pressed.

Key contents:
- ExportPanel: Preview, Export / Cancel, progress, summary and shutdown hook.
- _start_export: Snapshots the inputs and submits the worker.
- _refresh_preview: Recomputes the target-folder names from the range panel state.

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
from tkinter import ttk

from app.logic.scanalign import stack_service
from app.logic.scanalign.export_service import (
    RegistrationExporter,
    next_free_folder,
    output_folder_name,
    resolve_exp_number,
    resolve_name,
)
from app.view.shared.error_handler import handle_errors, show_error_popup
from app.view.shared.tool_tip import Tooltip

_MISSING = "—"
_PROGRESS_INTERVAL_S = 0.1  # at most 10 UI updates per second


class ExportPanel:
    """Controls in the ``scan_export`` frame for exporting the matched pairs."""

    def __init__(self, context, frame_key="scan_export"):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame(frame_key)
        self.viewers = {
            1: context.get_panel("scan_viewer_1"),
            2: context.get_panel("scan_viewer_2"),
        }
        self.range_panel = context.get_panel("scan_range")

        self._running = False
        self._closed = False
        self._exporter = None
        self._progress_lock = threading.Lock()
        self._last_ui_push = 0.0

        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-export")
        context.register_executor(self._executor)
        context.register_shutdown_hook(self.close)

        self._build()
        self.range_panel.add_change_listener(self._on_range_changed)
        self._refresh_preview()

    # ------------------------------------------------------------------ UI

    def _build(self):
        self.frame.columnconfigure(0, weight=1)
        preview = ttk.Frame(self.frame)
        preview.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        self.preview_labels = {}
        self.preview_tips = {}
        for slot in (1, 2):
            ttk.Label(preview, text=f"Scan {slot} →").grid(row=slot - 1, column=0, sticky="w")
            label = ttk.Label(preview, text=_MISSING)
            label.grid(row=slot - 1, column=1, sticky="w", padx=(6, 0))
            self.preview_labels[slot] = label
            self.preview_tips[slot] = Tooltip(label, text="No scan loaded", wraplength=320)

        buttons = ttk.Frame(self.frame)
        buttons.grid(row=1, column=0, sticky="ew", padx=6, pady=(8, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        self.export_button = ttk.Button(
            buttons, text="Export", command=self._start_export, bootstyle="success"
        )
        self.export_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.cancel_button = ttk.Button(
            buttons,
            text="Cancel",
            command=self._cancel,
            bootstyle="danger-outline",
            state="disabled",
        )
        self.cancel_button.grid(row=0, column=1, sticky="ew")

        progress = ttk.Frame(self.frame)
        progress.grid(row=2, column=0, sticky="ew", padx=6, pady=(6, 0))
        progress.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(progress, mode="determinate", maximum=100, length=120)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = ttk.Label(progress, text="", bootstyle="secondary", width=18)
        self.progress_label.grid(row=0, column=1, padx=(6, 0))

        self.summary_label = ttk.Label(self.frame, text="", wraplength=260, justify="left")
        self.summary_label.grid(row=3, column=0, sticky="w", padx=6, pady=(6, 6))

    # ------------------------------------------------------------ threading

    def _post(self, func, *args):
        """Run ``func`` on the Tk thread (safe from any thread, ignores a closed UI)."""
        with contextlib.suppress(RuntimeError, tk.TclError):
            self.root.after(0, func, *args)

    # -------------------------------------------------------------- preview

    @handle_errors("ScanAlign export range change")
    def _on_range_changed(self):
        if not self._running:
            self._refresh_preview()

    def _target_names(self):
        """``{slot: (folder name, parent)}`` for the current pairs, or ``None``."""
        pairs = self.range_panel.pairs
        stacks = (self.viewers[1].stack, self.viewers[2].stack)
        if not pairs or any(s is None for s in stacks):
            return None
        names = {}
        for slot, stack in zip((1, 2), stacks, strict=True):
            parent = stack.folder.parent
            base = output_folder_name(resolve_exp_number(stack), resolve_name(stack), len(pairs))
            names[slot] = (next_free_folder(parent, base), parent)
        return names

    def _refresh_preview(self):
        names = self._target_names()
        for slot in (1, 2):
            if names is None:
                self.preview_labels[slot].configure(text=_MISSING)
                self.preview_tips[slot].text = "Set valid ranges and N for both scans"
            else:
                name, parent = names[slot]
                self.preview_labels[slot].configure(text=name)
                self.preview_tips[slot].text = f"Created in {parent}"
        self._update_buttons(ready=names is not None)

    def _update_buttons(self, ready=None):
        if ready is None:
            ready = bool(self.range_panel.pairs)
        self.export_button.configure(state="normal" if ready and not self._running else "disabled")
        self.cancel_button.configure(state="normal" if self._running else "disabled")

    # --------------------------------------------------------------- export

    @handle_errors("ScanAlign export")
    def _start_export(self):
        if self._running or self._closed:
            return
        pairs = self.range_panel.pairs
        ranges = self.range_panel.ranges
        stack1, stack2 = self.viewers[1].stack, self.viewers[2].stack
        if not pairs or ranges is None or stack1 is None or stack2 is None:
            return
        # Snapshot: later range / viewer changes must not affect the running export.
        comparison = stack_service.compare_geometry(stack1.geometry, stack2.geometry)
        exporter = RegistrationExporter()  # fresh per run: run() keeps the cancel flag
        self._exporter = exporter
        self._running = True
        self.summary_label.configure(text="")
        self.progress_bar["value"] = 0
        self.progress_label.configure(text="Starting…")
        self._update_buttons()
        try:
            self._executor.submit(
                self._export_worker, exporter, stack1, stack2, ranges, pairs, comparison
            )
        except RuntimeError:  # executor shut down
            self._running = False
            self._update_buttons()

    def _export_worker(self, exporter, stack1, stack2, ranges, pairs, comparison):
        """Worker thread: run the export, then hand the outcome to the Tk thread."""
        try:
            result = exporter.run(
                stack1,
                stack2,
                ranges[0],
                ranges[1],
                pairs,
                comparison,
                on_progress=self._on_progress,
            )
        except Exception as exc:  # noqa: BLE001 - reported to the user
            self._post(self._on_failed, exporter, exc, traceback.format_exc())
            return
        self._post(self._on_done, exporter, result, len(pairs))

    def _on_progress(self, done, total):
        """Worker thread: push to the UI at most 10x per second."""
        with self._progress_lock:
            now = time.monotonic()
            if now - self._last_ui_push < _PROGRESS_INTERVAL_S:
                return
            self._last_ui_push = now
        self._post(self._update_progress, done, total)

    def _update_progress(self, done, total):
        if not self._running or not total:
            return
        self.progress_bar["value"] = 100.0 * done / total
        self.progress_label.configure(text=f"Copying {done} / {total}")

    @handle_errors("ScanAlign cancel export")
    def _cancel(self):
        if self._exporter is not None and self._running:
            self._exporter.cancel()
            self.cancel_button.configure(state="disabled")
            self.progress_label.configure(text="Cancelling…")

    def _finish(self):
        self._running = False
        self._exporter = None
        self.progress_bar["value"] = 0
        self.progress_label.configure(text="")
        self._refresh_preview()  # the new folders exist now -> next names get a suffix

    @handle_errors("ScanAlign export done")
    def _on_done(self, exporter, result, n_pairs):
        if self._closed:
            return
        self._finish()
        if result.cancelled:
            self.summary_label.configure(text="Export cancelled — no folders left behind")
            self.context.safe_status_update("ScanAlign export cancelled", level="warning")
            return
        folder1, folder2 = result.folders
        self.summary_label.configure(
            text=f"Scan 1: {folder1}\nScan 2: {folder2}\n2 × {n_pairs} files"
        )
        self.context.safe_status_update(
            f"ScanAlign export finished: 2 × {n_pairs} files", level="success"
        )

    @handle_errors("ScanAlign export failed")
    def _on_failed(self, exporter, exc, tb):
        if self._closed:
            return
        self._finish()
        message = str(exc) if isinstance(exc, ValueError) else f"{exc}\n\n{tb}"
        show_error_popup("ScanAlign export failed", message)

    # ------------------------------------------------------------- shutdown

    def close(self):
        """Cancel a running export (shutdown hook; safe to call repeatedly)."""
        self._closed = True
        exporter = self._exporter
        if exporter is not None:
            exporter.cancel()
