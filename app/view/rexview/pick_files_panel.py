#!/usr/bin/env python3
"""
RexView Pick Files Panel.

Folder and file picker that discovers OCT archives and populates the export
queue. Supports recursive folder scanning and optional text-file import of
pre-defined slice ranges. Uses FileDiscoveryService for headless scanning.

Key contents:
- pickFilesPanel: Panel with Select Folder / Select File(s) buttons.
- globalPickerThread: Background thread for recursive OCT discovery.
- populate_queue: Adds discovered files to the TreeView queue with default settings.
- Text file import: Parses companion .txt files for slice range hints.

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
from concurrent import futures
from pathlib import Path
from tkinter import filedialog, ttk

from app.logic.rexview import FileDiscoveryService
from app.logic.shared import oct_functions as octF
from app.view.shared import dialogs
from app.view.shared.error_handler import handle_errors
from app.view.shared.tool_tip import Tooltip


class pickFilesPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("pick_files")
        self.treeView = self.context.get_panel("tree")
        self.globalSettings = self.context.get_panel("global_settings")

        # Initialize FileDiscoveryService with XML reader
        self._file_discovery_service = FileDiscoveryService(
            xml_dict_reader=octF.getXMLDiscoveryInfo
        )

        # Reused single-worker executor for the picker background thread.
        # max_workers=1 already serializes runs, so one long-lived executor
        # avoids leaking a fresh non-daemon thread pool on every click.
        self._picker_executor = futures.ThreadPoolExecutor(max_workers=1)
        self.context.register_executor(self._picker_executor)

        # Add buttons and instructions here
        self.pickFolderToolTip = (
            "Choose a folder whichs contains at least one OCT file. "
            "All OCT Files inside this folder and subfolders are detected and added "
            "to the queue. \n\n"
            "To supply export range, equidistant slices and refractive index for an "
            "OCT file, place a text file with the exact same name (e.g. scan.oct -> "
            "scan.txt) in the same folder. \n\n"
            "If no exact match exists, a text file named after the specimen base name "
            "(the file name without a trailing run-counter/mode suffix, e.g. "
            "scan_0002_Mode3D.oct -> scan.txt) is used instead, as long as it is "
            "unambiguous. If several scans in the folder share that base name and none "
            "of them has its own exact-named text file, the base-name text file is "
            "applied only to the scan with the highest run counter (the newest kept "
            "attempt); the others fall back to default settings. \n\n"
            "Each line defines one export direction as VIEW:START-END:COUNT:RI (all "
            "parts but the range are optional): \n"
            " 33-444\n"
            " 33-444:25\n"
            " XZ:33-444:25\n"
            " XZ:33-444:25:1.35"
        )
        self.pickFolderBtn = ttk.Button(
            self.frame,
            text="Select Folder",
            width=14,
            command=lambda: self.globalPickerThread(1),
            bootstyle="primary",
        )
        self.pickFolderBtn.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.pickFolderBtn, text=self.pickFolderToolTip, wraplength=200)

        self.button_label = ttk.Label(self.frame, text="  ")
        self.button_label.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.pickFileToolTip = "Choose a single OCT file."
        self.pickFileBtn = ttk.Button(
            self.frame,
            text="Select File",
            width=14,
            command=lambda: self.globalPickerThread(0),
            bootstyle="info",
        )
        self.pickFileBtn.grid(row=0, column=2, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.pickFileBtn, text=self.pickFileToolTip, wraplength=200)

        self.button_label = ttk.Label(self.frame, text="  ")
        self.button_label.grid(row=0, column=3, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.deleteFileToolTip = "Delete one or more selected items in the queue."
        self.deleteEntryBtn = ttk.Button(
            self.frame,
            text="Delete Entry(s)",
            width=14,
            command=self.treeView.deleteEntry,
            bootstyle="warning",
        )
        self.deleteEntryBtn.grid(row=0, column=4, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.deleteEntryBtn, text=self.deleteFileToolTip, wraplength=200)

        self.button_label = ttk.Label(self.frame, text="  ")
        self.button_label.grid(row=0, column=5, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.showBtnToolTip = "Select a OCT-Scan from the queue and display it."
        self.showBtn = ttk.Button(
            self.frame,
            text="Show",
            width=14,
            command=lambda: self.context.get_panel("rex_image").dispImageInCanvas(),
            bootstyle="success",
        )
        self.showBtn.grid(row=0, column=6, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.showBtn, text=self.showBtnToolTip, wraplength=200)

        # %% folder/file Picker

    @handle_errors("pickFilesPanel")
    def globalPickerThread(self, var):
        """
        To prevent GUII from freezing during a loop or time consuming function
        call, we need to set up threads.
        In this thread we call the mainRoutines.

        Returns
        -------
        None.

        """
        # print('starting')
        self.running = 0
        # run on the shared background executor to keep UI responsive
        self._picker_executor.submit(self.globalPicker, var)

    @handle_errors("pickFilesPanel")
    def globalPicker(self, isFolder: bool):
        """
        Uses file open or ask directory dialog to list oct file(s) in the
        directory.

        Parameters
        ----------
        isFolder : bool
            1 if one chooses a folder
            0 if one chooses a file.

        Returns
        -------
        None

        """

        global dir
        if isFolder == 1:
            selected_path = filedialog.askdirectory(
                initialdir=dir, title="Select the Folder Containing Your OCT Files!"
            )
            if not selected_path:
                return

            self.folderPath = Path(selected_path)
            tmpPathList = self._collect_oct_files(self.folderPath)

            if not tmpPathList:
                dialogs.show_info(
                    self.root,
                    "No OCT Files Found",
                    f"No OCT files were found in:\n{self.folderPath}\n\n"
                    "Please choose another folder.",
                )
                self.context.safe_status_update(
                    "No OCT files found in selected folder.", level="warning"
                )
                return

            self.tmpFileList = []
            self._create_progress_popup(len(tmpPathList))

            try:
                self.tmpFileList = self._process_files_parallel(tmpPathList)
            finally:
                self._destroy_progress_popup()

            if self.running == 1:
                return

        else:
            selected_path = filedialog.askopenfilename(
                initialdir=dir,
                title="Select One OCT File!",
                filetypes=(("All Files", "*.*"), ("OCT Files", "*.oct")),
            )

            if not selected_path:
                return

            self.filePath = Path(selected_path)

            if not self.filePath.exists():
                dialogs.show_error(
                    self.root,
                    "File Not Found",
                    f"The selected file could not be located:\n{self.filePath}",
                )
                self.context.safe_status_update("Selected file not found.", level="error")
                return

            self.tmpFileList = self._build_entries_for_file(self.filePath)

        if not getattr(self, "tmpFileList", []):
            return

        self.treeView.setMultipleValues(self.tmpFileList)
        count = len(self.tmpFileList)
        self.context.safe_status_update(f"Added {count} item(s) to export queue.", level="success")

    # %%
    def _collect_oct_files(self, folder_path: Path):
        """
        Collect OCT files from a directory using FileDiscoveryService.

        Parameters
        ----------
        folder_path : Path
            Directory to scan for OCT files

        Returns
        -------
        list
            Sorted list of OCT file paths
        """
        result = self._file_discovery_service.scan_directory(folder_path, recursive=True)
        return result.files

    def _create_progress_popup(self, total_files: int):
        self.running = 0
        self._progress_total = total_files
        self._progress_step = max(1, total_files // 100)
        self.popup = tk.Toplevel(self.root)
        tk.Label(
            self.popup, text="Searching for OCT files in selected folder. This might take a while."
        ).grid(row=0, column=0)
        self.progress_var = tk.DoubleVar(value=0)
        self.progressBar = ttk.Progressbar(
            self.popup,
            variable=self.progress_var,
            maximum=total_files,
            orient="horizontal",
            mode="determinate",
            length=280,
        )
        self.progressBar.grid(row=1, column=0)
        self.cancelButton = ttk.Button(self.popup, text="Cancel!", command=self.breakAll)
        self.cancelButton.grid(column=0, row=2, padx=10, pady=10, sticky=tk.E)
        self.popup.pack_slaves()

    def _update_progress_popup(self, value: int):
        if hasattr(self, "progress_var"):
            self.progress_var.set(value)
        # A full Tk redraw per file is expensive and dominates the loop for
        # large folders. Throttle to every Nth file (and always the last one).
        total = getattr(self, "_progress_total", None)
        step = getattr(self, "_progress_step", 1)
        if value % step != 0 and value != total:
            return
        if hasattr(self, "popup") and self.popup.winfo_exists():
            self.popup.update()

    def _destroy_progress_popup(self):
        if hasattr(self, "popup"):
            try:
                if self.popup.winfo_exists():
                    self.popup.destroy()
            except tk.TclError:
                pass
            finally:
                self.popup = None

    def _process_files_parallel(self, file_paths):
        """
        Extract metadata and sidecar settings for multiple OCT files concurrently.

        Each file's zip/XML read and sidecar resolution (FileDiscoveryService
        .process_file, pure logic with no Tk calls) is dispatched to a small
        worker pool so their I/O overlaps instead of serializing, which
        matters most on network drives. Error dialogs and TreeView value
        conversion happen back on this (background picker) thread, since
        they must not run concurrently from multiple threads.

        Parameters
        ----------
        file_paths : list
            OCT file paths to process, in the desired result order.

        Returns
        -------
        list
            Flattened list of entry tuples for TreeView, in file_paths order.
        """
        show_errors = self.globalSettings.getErrorState() == "selected"
        max_workers = min(8, max(1, len(file_paths)))

        results = [None] * len(file_paths)
        with futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_index = {
                pool.submit(self._file_discovery_service.process_file, Path(fp), show_errors): i
                for i, fp in enumerate(file_paths)
            }
            for completed, future in enumerate(futures.as_completed(future_to_index), start=1):
                index = future_to_index[future]
                if self.running == 1:
                    break
                results[index] = future.result()
                self._update_progress_popup(completed)

        entries = []
        for result in results:
            if result is None:
                continue
            items, error_msg = result
            if error_msg:
                dialogs.show_error(self.root, "Metadata File Issue", error_msg)
            entries.extend(list(item.to_treeview_values()) for item in items)
        return entries

    def _build_entries_for_file(self, file_path: Path):
        """
        Build queue entries for a single OCT file.

        Uses FileDiscoveryService for metadata extraction and default values.

        Parameters
        ----------
        file_path : Path
            Path to OCT file

        Returns
        -------
        list
            List of entry tuples for TreeView
        """
        file_path = Path(file_path)
        show_errors = self.globalSettings.getErrorState() == "selected"

        # Delegate validation, metadata extraction, sidecar parsing and
        # queue-item construction to the service (single OCT zip read path).
        items, error_msg = self._file_discovery_service.process_file(
            file_path,
            show_errors=show_errors,
        )

        if error_msg:
            dialogs.show_error(self.root, "Metadata File Issue", error_msg)

        return [list(item.to_treeview_values()) for item in items]

    def getFilePath(self) -> str:
        """


        Returns
        -------
        str
            DESCRIPTION.

        """
        return self.filePath

    # %%

    def breakAll(self):
        """
        Var for MainRoutine to break the export cycle.

        Returns
        -------
        None.

        """
        self.running = 1
        self.context.safe_status_update("File scan cancelled.", level="warning")
        self.popup.destroy()
