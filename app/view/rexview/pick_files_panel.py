#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from tkinter import ttk
from app.view.shared.tool_tip import Tooltip
from tkinter import filedialog
from pathlib import Path
from concurrent import futures
from app.view.shared.error_handler import handle_errors
from app.logic.shared import oct_functions as octF
from app.logic.rexview import FileDiscoveryService
from app.view.shared import dialogs


class pickFilesPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("pick_files")
        self.treeView = self.context.get_panel("tree")
        self.globalSettings = self.context.get_panel("global_settings")

        # Initialize FileDiscoveryService with XML reader
        self._file_discovery_service = FileDiscoveryService(xml_dict_reader=octF.getXMLDiscoveryInfo)

        # Add buttons and instructions here
        self.pickFolderToolTip = 'Choose a folder whichs contains at least one OCT file. ' \
            'All OCT Files inside this folder and subfolders are detected and added to the queue. \n\n' \
            'If you supply a plain text file within a OCT-File directory [*.txt] with information about export range ' \
            'and equidistant slices, those parameters are imported. \n\n' \
            'Format example: \n 33-444 \n 25'
        self.pickFolderBtn = ttk.Button(self.frame,
                                        text='Select Folder',
                                        width=14,
                                        command=lambda: self.globalPickerThread(1),
                                        bootstyle="primary")
        self.pickFolderBtn.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.pickFolderBtn, text=self.pickFolderToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.pickFileToolTip = 'Choose a single OCT file.'
        self.pickFileBtn = ttk.Button(self.frame,
                                      text='Select File',
                                      width=14,
                                      command=lambda: self.globalPickerThread(0),
                                      bootstyle="info")
        self.pickFileBtn.grid(row=0, column=2, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.pickFileBtn, text=self.pickFileToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid( row=0, column=3, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.deleteFileToolTip = 'Delete one or more selected items in the queue.'
        self.deleteEntryBtn = ttk.Button(self.frame,
                                         text='Delete Entry(s)',
                                         width=14,
                                         command=self.treeView.deleteEntry,
                                         bootstyle="warning")
        self.deleteEntryBtn.grid(row=0, column=4, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.deleteEntryBtn, text=self.deleteFileToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid( row=0, column=5, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.showBtnToolTip = 'Select a OCT-Scan from the queue and display it.'
        self.showBtn = ttk.Button(self.frame,
                                  text='Show',
                                  width=14,
                                  command=lambda: self.context.get_panel("rex_image").dispImageInCanvas(),
                                  bootstyle="success")
        self.showBtn.grid(row=0, column=6, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        Tooltip(self.showBtn, text=self.showBtnToolTip , wraplength=200)

        #%% folder/file Picker

    @handle_errors("pickFilesPanel")
    def globalPickerThread(self, var):
        '''
        To prevent GUII from freezing during a loop or time consuming function
        call, we need to set up threads.
        In this thread we call the mainRoutines.

        Returns
        -------
        None.

        '''
        #print('starting')
        self.running = 0
        # create a thread to keep UI responsive
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.globalPicker, var)


    @handle_errors("pickFilesPanel")
    def globalPicker(self, isFolder: bool):
        '''
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

        '''

        global dir
        if isFolder == 1:
            selected_path = filedialog.askdirectory(initialdir=dir,
                                                     title='Select the Folder Containing Your OCT Files!')
            if not selected_path:
                return

            self.folderPath = Path(selected_path)
            tmpPathList = self._collect_oct_files(self.folderPath)

            if not tmpPathList:
                dialogs.show_info(
                    self.root,
                    "No OCT Files Found",
                    f"No OCT files were found in:\n{self.folderPath}\n\nPlease choose another folder."
                )
                return

            self.tmpFileList = []
            self._create_progress_popup(len(tmpPathList))

            try:
                for index, file_path in enumerate(tmpPathList, start=1):
                    if self.running == 1:
                        break
                    self.tmpFileList.extend(self._build_entries_for_file(Path(file_path)))
                    self._update_progress_popup(index)
            finally:
                self._destroy_progress_popup()

            if self.running == 1:
                return

        else:

            selected_path = filedialog.askopenfilename(initialdir=dir,
                                                        title='Select One OCT File!',
                                                        filetypes=(('All Files', '*.*'),
                                                                   ('OCT Files', '*.oct')))

            if not selected_path:
                return

            self.filePath = Path(selected_path)

            if not self.filePath.exists():
                dialogs.show_error(
                    self.root,
                    "File Not Found",
                    f"The selected file could not be located:\n{self.filePath}"
                )
                return

            self.tmpFileList = self._build_entries_for_file(self.filePath)

        if not getattr(self, "tmpFileList", []):
            return

        self.treeView.setMultipleValues(self.tmpFileList)
        self.root.destroy


    #%%
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
        tk.Label(self.popup, text="Searching for OCT files in selected folder. This might take a while.").grid(row=0, column=0)
        self.progress_var = tk.DoubleVar(value=0)
        self.progressBar = ttk.Progressbar(self.popup,
                                           variable=self.progress_var,
                                           maximum=total_files,
                                           orient='horizontal',
                                           mode='determinate',
                                           length=280)
        self.progressBar.grid(row=1, column=0)
        self.cancelButton = ttk.Button(self.popup, text='Cancel!', command=self.breakAll)
        self.cancelButton.grid(column=0, row=2, padx=10, pady=10, sticky=tk.E)
        self.popup.pack_slaves()

    def _update_progress_popup(self, value: int):
        if hasattr(self, 'progress_var'):
            self.progress_var.set(value)
        # A full Tk redraw per file is expensive and dominates the loop for
        # large folders. Throttle to every Nth file (and always the last one).
        total = getattr(self, '_progress_total', None)
        step = getattr(self, '_progress_step', 1)
        if value % step != 0 and value != total:
            return
        if hasattr(self, 'popup') and self.popup.winfo_exists():
            self.popup.update()

    def _destroy_progress_popup(self):
        if hasattr(self, 'popup'):
            try:
                if self.popup.winfo_exists():
                    self.popup.destroy()
            except tk.TclError:
                pass
            finally:
                self.popup = None

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

    def getFilePath(self)->str:
        """


        Returns
        -------
        str
            DESCRIPTION.

        """
        return self.filePath

# %%

    def breakAll(self):
        '''
        Var for MainRoutine to break the export cycle.

        Returns
        -------
        None.

        '''
        self.running = 1
        self.popup.destroy()