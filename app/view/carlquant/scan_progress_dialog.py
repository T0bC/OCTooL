"""
CarlQuant Folder Scan Progress Dialog.

Modal dialog shown while loadImagePanel discovers and loads specimens: first
`DataLoader.find_image_stacks` walking the selected folder tree, then
`DataLoader.load_specimen_config` reading each specimen's config JSON. Config
files often live on the same slow/network drive, so that second phase can take
just as long as the folder walk and must stay visible too, or the app looks
frozen right after "found" specimens flash by. Phase 1's total is unknown
until the walk finishes, so it uses an indeterminate bar; phase 2 knows the
specimen count up front and switches to a determinate one.

Key contents:
- ScanProgressDialog: Thread-safe modal dialog spanning both load phases.
- update: Advances the folder-scan status from the worker thread.
- start_config_phase / update_config: Switches to and advances config loading.
- finish: Stops the animation and closes the dialog.

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


class ScanProgressDialog:
    """Modal, indeterminate progress dialog for folder scanning."""

    def __init__(self, parent, root_folder_name):
        self.parent = parent

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Scanning Folder")
        self.dialog.geometry("450x150")
        self.dialog.resizable(False, False)

        self.dialog.transient(parent)
        self.dialog.grab_set()
        # Scanning is not cancellable, so ignore the close button rather than
        # tearing down a dialog the worker thread is still writing to.
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: None)

        self._center_dialog()
        self._build_ui(root_folder_name)

    def _center_dialog(self):
        self.dialog.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        dialog_width = self.dialog.winfo_width()
        dialog_height = self.dialog.winfo_height()
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _build_ui(self, root_folder_name):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.title_label = ttk.Label(
            main_frame,
            text=f"Scanning '{root_folder_name}' for image stacks...",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.title_label.pack(anchor=tk.W)

        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(10, 10))
        self.progress.start(15)

        self.count_label = ttk.Label(main_frame, text="Folders scanned: 0 | Specimens found: 0")
        self.count_label.pack(anchor=tk.W)

        self.path_label = ttk.Label(main_frame, text="", foreground="gray", wraplength=410)
        self.path_label.pack(anchor=tk.W, pady=(5, 0))

    def update(self, folders_scanned, specimens_found, current_path):
        """Update folder-scan status (phase 1). Safe to call from a worker thread."""

        def _update():
            self.count_label.config(
                text=f"Folders scanned: {folders_scanned} | Specimens found: {specimens_found}"
            )
            self.path_label.config(text=str(current_path))

        self.dialog.after(0, _update)

    def start_config_phase(self, total_specimens):
        """Switch to phase 2 (loading each specimen's config). Total is now known,
        so the bar becomes determinate instead of indeterminate."""

        def _update():
            self.progress.stop()
            self.progress.config(mode="determinate", maximum=max(total_specimens, 1), value=0)
            self.title_label.config(text="Loading specimen configuration...")
            self.count_label.config(text=f"Specimen 0 of {total_specimens}")
            self.path_label.config(text="")

        self.dialog.after(0, _update)

    def update_config(self, loaded, total, specimen_name):
        """Advance phase-2 progress. Safe to call from a worker thread."""

        def _update():
            self.progress["value"] = loaded
            self.count_label.config(text=f"Specimen {loaded} of {total}")
            self.path_label.config(text=str(specimen_name))

        self.dialog.after(0, _update)

    def finish(self):
        """Stop the animation and close the dialog. Safe from a worker thread."""

        def _finish():
            self.progress.stop()
            self.close()

        self.dialog.after(0, _finish)

    def close(self):
        try:
            self.dialog.grab_release()
            self.dialog.destroy()
        except Exception:
            pass  # Dialog may already be destroyed
