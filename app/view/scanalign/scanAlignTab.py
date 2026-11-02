"""
ScanAlign Tab.

Composes the ScanAlign tab: a left controls column (Load / Slice Matching / Export)
and two scan viewers stacked vertically with a thin link strip between them.

Key contents:
- addContent: Lays out the ScanAlign frames, creates the panels and registers them.

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

from app.view.scanalign.link_strip import LinkStrip
from app.view.scanalign.load_panel import LoadPanel
from app.view.scanalign.stack_viewer_panel import StackViewerPanel
from app.view.shared.error_handler import handle_errors


@handle_errors("scanAlignTab.addContent")
def addContent(self, frame):
    self.scanAlignTabFrame = frame
    self.context.root = self.scanAlignTabFrame
    self.attach_status_bar(self.context)

    # Column 0 -> controls (spanning all rows), column 1 -> viewer 1, the link strip
    # and viewer 2 stacked vertically (B-scans are wider than tall, so stacking uses
    # the screen height and gives each viewer the full width). Viewers share height equally.
    frame.columnconfigure(0, weight=0)
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1, uniform="viewers")
    frame.rowconfigure(1, weight=0)
    frame.rowconfigure(2, weight=1, uniform="viewers")

    # Controls container (Load / Range / Export)
    self.scanControlsContainer = ttk.Frame(frame)
    self.scanControlsContainer.grid(row=0, column=0, rowspan=3, sticky="nsw", padx=5, pady=5)

    sections = (
        ("scanLoadFrame", "Load Scans", "scan_load", False),
        ("scanRangeFrame", "Slice Matching", "scan_range", True),
        ("scanExportFrame", "Export", "scan_export", True),
    )
    for attr, text, key, placeholder in sections:
        section = ttk.LabelFrame(self.scanControlsContainer, text=text, relief=tk.RIDGE)
        section.pack(fill="x", pady=(0, 2))
        if placeholder:
            ttk.Label(section, text="Available in a later version", bootstyle="secondary").pack(
                padx=10, pady=10
            )
        setattr(self, attr, section)
        self.context.register_frame(key, section)

    # Viewers and the link strip between them
    self.scanViewer1Frame = ttk.LabelFrame(frame, text="Scan 1 (reference)")
    self.scanViewer1Frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("scan_viewer_1", self.scanViewer1Frame)

    self.scanLinkFrame = ttk.Frame(frame)
    self.scanLinkFrame.grid(row=1, column=1, sticky="ew", padx=5)
    self.context.register_frame("scan_link", self.scanLinkFrame)

    self.scanViewer2Frame = ttk.LabelFrame(frame, text="Scan 2 (moving)")
    self.scanViewer2Frame.grid(row=2, column=1, sticky="nsew", padx=5, pady=5)
    self.context.register_frame("scan_viewer_2", self.scanViewer2Frame)

    # Panels; the load panel is created last because it looks up the others.
    self.scanViewer1 = StackViewerPanel(self.context, "scan_viewer_1", role=1)
    self.context.register_panel("scan_viewer_1", self.scanViewer1)

    self.scanViewer2 = StackViewerPanel(self.context, "scan_viewer_2", role=2)
    self.context.register_panel("scan_viewer_2", self.scanViewer2)

    self.scanLinkStrip = LinkStrip(self.context, "scan_link")
    self.context.register_panel("scan_link", self.scanLinkStrip)

    self.scanLoadPanel = LoadPanel(self.context, "scan_load")
    self.context.register_panel("scan_load", self.scanLoadPanel)
