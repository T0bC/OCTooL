#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils.tool_tip import Tooltip
from tkinter import filedialog, messagebox
from pathlib import Path
import os
from fnmatch import fnmatch
from utils import oct_functions as octF
from concurrent import futures
from utils.error_handler import handle_errors
from app.logic.rexview import FileDiscoveryService


class pickFilesPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("pick_files")
        self.treeView = self.context.get_panel("tree")
        self.globalSettings = self.context.get_panel("global_settings")

        # Initialize FileDiscoveryService with XML reader
        self._file_discovery_service = FileDiscoveryService(xml_reader=octF.getXMLvalue)

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
                self.show_info_box(
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
                self.show_error_box(
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
            self.show_error_box("Metadata File Issue", error_msg)

        return [list(item.to_treeview_values()) for item in items]

    def getFilePath(self)->str:
        """


        Returns
        -------
        str
            DESCRIPTION.

        """
        return self.filePath

    def parse_metadata_file(self, file_path: Path) -> dict:
        """
        Parses a metadata sidecar file for 2D slice export settings.

        The metadata file is expected to contain lines specifying the view direction (XZ, YZ, XY),
        slice range (start-end), and the number of equidistant slices to export. Each line follows
        the format: <VIEW>:<START-END>:<COUNT>

        Supports partial lines with missing fields. Defaults:
            - View: XZ
            - numAequidistSlices: calculated as end - start + 1
            - refractiveIndex: 1.0

        Format:
        <VIEW(optional)>:<START-END>:<COUNT(optional)>:<REFRACTIVE(optional)>
        Examples:
        ":10-50::" (defaults to XZ, 41 slices, RI=1.0)
        "YZ:20-80:15:" (defaults RI to 1.0)
        "XY:25-90::1.33" (defaults COUNT to 66)

        Parameters
        ----------
        file_path : Path
            Path to the metadata .txt file. Point directly to the text file containing export instructions.

        Raises
        ------
        ValueError
            Raised if a line is incorrectly formatted or contains invalid numeric values.
        RuntimeError
            Raised if the file cannot be opened or parsed for any reason, such as file I/O errors.

        Returns
        -------
        dict
            Dictionary with view keys (`XZ`, `YZ`, `XY`) mapping to a configuration dictionary.
            Each configuration dictionary contains:
                - 'start': int, beginning slice index
                - 'end'  : int, ending slice index
                - 'numAequidistSlices': int, number of equidistant slices to export
                - 'refractiveIndex': float, value for the refractive index

        Example
        -------
        XZ:20-80:20:1
        YZ:15-90:10:1

        Returns:
        {
            'XZ': {'start': 20, 'end': 80, 'numAequidistSlices': 20, 'refractiveIndex': 1},
            'YZ': {'start': 15, 'end': 90, 'numAequidistSlices': 10, 'refractiveIndex': 1.5}
        }
        """

        export_settings = {}

        def parse_line(line):
            # Split by colon or fallback to full line
            tokens = line.strip().split(":")
            tokens = [t.strip() for t in tokens if t.strip()]

            view = "XZ"
            range_str = None
            count = None
            ri = 1.0

            if len(tokens) == 1 and "-" in tokens[0]:  # Only range, no view
                range_str = tokens[0]
            elif len(tokens) == 2 and "-" in tokens[0]:  # Range and count/RI?
                range_str = tokens[0]
                try:
                    count = int(tokens[1])
                except ValueError:
                    ri = float(tokens[1])
            elif len(tokens) == 3 and "-" in tokens[1]:  # View + range + count
                view = tokens[0].upper()
                range_str = tokens[1]
                count = int(tokens[2])
            elif len(tokens) == 4:  # All fields present
                view = tokens[0].upper()
                range_str = tokens[1]
                count = int(tokens[2])
                ri = float(tokens[3])
            else:
                raise ValueError(f"Unrecognized format in line: {line}")

            try:
                start, end = map(int, range_str.split("-"))
            except Exception:
                raise ValueError(f"Invalid range format: {range_str}")

            if count is None:
                count = end - start

            return view, {
                "start": start,
                "end": end,
                "numAequidistSlices": count,
                "refractiveIndex": ri
            }

        try:
            with open(file_path, "r") as f:
                for line in f:
                    if not line.strip() or line.startswith("#"):
                        continue
                    view, config = parse_line(line)
                    export_settings[view] = config

        except Exception as e:
            raise RuntimeError(f"Failed to parse metadata file: {e}")

        return export_settings


    def show_error_box(self, title: str, message: str):
        """
        Displays a user-friendly error message using a Tkinter popup window.

        This function creates a temporary, hidden Tkinter root window solely
        for showing a messagebox dialog. It's useful for communicating parsing
        or file I/O issues in a GUI application.

        Parameters
        ----------
        title : str
            Title of the error message box window.
        message : str
            Detailed message describing the error to the user.

        Returns
        -------
        None
        """

        root_err = tk.Tk()
        root_err.withdraw()  # Hide the main window
        tk.messagebox.showerror(title, message)
        root_err.destroy()   # Close the Tk instance

    def show_info_box(self, title: str, message: str):
        root_info = tk.Tk()
        root_info.withdraw()
        messagebox.showinfo(title, message)
        root_info.destroy()

    def handle_metadata_parsing(self, file_path: Path, dimY: int) -> dict:
        """
        Parses a metadata sidecar file and applies fallback if the file does not exist
        or is malformed. Displays any issues via a user-friendly messagebox.

        Parameters
        ----------
        file_path : Path
            Path to the .txt metadata sidecar file.
        dimY : int
            Vertical dimension from the .oct scan used for default range calculation.

        Returns
        -------
        dict
            Dictionary with export settings either from file or fallback:
            {
                'XZ': {'start': 1, 'end': dimY, 'numAequidistSlices': dimY}
            }
        """
        show_errors = self.globalSettings.getErrorState() == "selected"
        
        # Use FileDiscoveryService for metadata parsing
        settings, error_msg = self._file_discovery_service.handle_metadata_parsing(
            file_path,
            dim_y=dimY,
            show_errors=show_errors,
        )
        
        if error_msg:
            self.show_error_box("Metadata File Issue", error_msg)
        
        # Convert ExportSettings models to dict format for backward compatibility
        result = {}
        for direction, export_settings in settings.items():
            result[direction] = {
                'start': export_settings.start,
                'end': export_settings.end,
                'numAequidistSlices': export_settings.num_equidistant_slices,
                'refractiveIndex': export_settings.refractive_index,
            }
        return result

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