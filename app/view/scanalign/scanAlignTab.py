"""
ScanAlign Tab.

Composes the ScanAlign tab skeleton: a left controls column (Load / Slice Matching /
Export) and two scan viewers stacked vertically. Phase 0 shows placeholders and the
getting-started instructions only.

Key contents:
- addContent: Lays out the ScanAlign frames and registers them in AppContext.
- _add_instruction_canvas: Temporary instruction canvas for a viewer frame.

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

from app.logic.shared.paths import resource_path
from app.view.shared.error_handler import handle_errors
from app.view.shared.instruction_renderer import InstructionRenderer

_INSTRUCTION_KEY = "scanalign_getting_started"


@handle_errors("scanAlignTab._add_instruction_canvas")
def _add_instruction_canvas(parent, instruction_key):
    """Fill ``parent`` with a canvas showing the getting-started instructions.

    Temporary stand-in until Phase 1's ``stack_viewer_panel`` replaces it.
    The canvas requests a small size (480x360) so the stacked viewers fit on
    smaller screens; Phase 1 must likewise shrink ``BaseCanvasPanel``'s 1024x480 request.
    """
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)

    canvas = tk.Canvas(parent, width=480, height=360, highlightthickness=0, bg="#505050")
    canvas.grid(row=0, column=0, sticky="nsew")

    renderer = InstructionRenderer(canvas)
    renderer.set_logo(resource_path("icons/WBM_UL_RGB_digital_Path.png"))

    pending = {"id": None}

    @handle_errors("scanAlignTab._render")
    def _render():
        pending["id"] = None
        renderer.render(instruction_key)

    @handle_errors("scanAlignTab._on_configure")
    def _on_configure(_event=None):
        if pending["id"] is not None:
            canvas.after_cancel(pending["id"])
        pending["id"] = canvas.after(100, _render)

    canvas.bind("<Configure>", _on_configure)
    pending["id"] = canvas.after(100, _render)
    return canvas


@handle_errors("scanAlignTab.addContent")
def addContent(self, frame):
    self.scanAlignTabFrame = frame
    self.context.root = self.scanAlignTabFrame
    self.attach_status_bar(self.context)

    # Column 0 -> controls (spanning both rows), column 1 -> the two viewers
    # stacked vertically (B-scans are wider than tall, so stacking uses the
    # screen height and gives each viewer the full width). Rows share height equally.
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1, uniform="viewers")
    frame.rowconfigure(1, weight=1, uniform="viewers")

    # Controls container (Load / Range / Export)
    self.scanControlsContainer = ttk.Frame(frame)
    self.scanControlsContainer.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=5, pady=5)

    sections = (
        ("scanLoadFrame", "Load Scans", "scan_load"),
        ("scanRangeFrame", "Slice Matching", "scan_range"),
        ("scanExportFrame", "Export", "scan_export"),
    )
    for attr, text, key in sections:
        section = ttk.LabelFrame(self.scanControlsContainer, text=text, relief=tk.RIDGE)
        section.pack(fill="x", pady=(0, 2))
        ttk.Label(section, text="Available in a later version", bootstyle="secondary").pack(
            padx=10, pady=10
        )
        setattr(self, attr, section)
        self.context.register_frame(key, section)

    # Viewers
    self.scanViewer1Frame = ttk.LabelFrame(frame, text="Scan 1 (reference)")
    self.scanViewer1Frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("scan_viewer_1", self.scanViewer1Frame)

    self.scanViewer2Frame = ttk.LabelFrame(frame, text="Scan 2 (moving)")
    self.scanViewer2Frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("scan_viewer_2", self.scanViewer2Frame)

    _add_instruction_canvas(self.scanViewer1Frame, _INSTRUCTION_KEY)
    _add_instruction_canvas(self.scanViewer2Frame, _INSTRUCTION_KEY)
