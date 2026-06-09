#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from concurrent import futures
from app.view.shared.tool_tip import Tooltip
from app.view.shared.error_handler import handle_errors

# Import refactored logic components
from app.logic.rexview import (
    ExportConfig,
    SliceExportParams,
    ExportService,
    ParallelExportCoordinator,
)
from app.view.rexview.gui_adapters import (
    export_config_from_gui_state,
    slice_export_params_from_treeview_row,
)


# %% To Prevent GUI Freezing during a long loop or function we need to set up
# threads.
#threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)

class executionPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("execution")
        self.treeView = self.context.get_panel("tree")
        self.imageFrame = self.context.get_panel("rex_image")
        self.globalSettingsFrame = self.context.get_panel("global_settings")
        self.customSettingsFrame = self.context.get_panel("custom_settings")
        self.mainWin = self.context.main_win
        
        # Initialize the export service (pure logic, no GUI dependencies)
        self.export_service = ExportService()
        # Coordinator for process-parallel, file-level export.
        self.export_coordinator = ParallelExportCoordinator()
        # Maps a file path to the queued TreeView item ids awaiting a result.
        self._items_by_path = {}

        self.executeBtn = ttk.Button(self.frame, text='RexView!', width=10,
                                     command=self.mainRoutine,
                                     bootstyle="success")
        self.executeBtn.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S)
        self.exportToolTip = "Start exporting of all entrys in queue."
        Tooltip(self.executeBtn, text=self.exportToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid(
            row=0, column=2, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.breakBtn = ttk.Button(self.frame, text='Cancel!', width=10,
                                   command=self.breakAll,
                                   bootstyle="warning")
        self.breakBtn.grid(row=0, column=3, sticky=tk.E + tk.W + tk.N + tk.S)
        self.stoppToolTip = "Stopp export."
        Tooltip(self.breakBtn, text=self.stoppToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid(
            row=0, column=4, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)


        self.quitBtn = ttk.Button(self.frame, text='Quit!', width=10,
                                  command=self.endProgram,
                                  bootstyle="danger")
        self.quitBtn.grid(row=0, column=5, sticky=tk.E + tk.W + tk.N + tk.S)
        self.quitToolTip = "Exits the application."
        Tooltip(self.quitBtn, text=self.quitToolTip , wraplength=200)

        # %%
    @handle_errors("executionPanel")
    def mainRoutine(self):
        '''
        Gather the export queue on the UI thread (tkinter widgets must only be
        read from the main thread), then dispatch the actual export to a
        background thread that drives the ParallelExportCoordinator.

        Returns
        -------
        None.

        '''
        self.running = 0
        self.export_service.reset()
        self.export_coordinator.reset()

        # Build the task list and the path -> items mapping on the UI thread.
        config = self._collect_export_config()
        tasks = []
        self._items_by_path = {}
        for item in self.treeView.getChildren():
            file_path = self.treeView.getValueFromRow(item, column='Path')
            params = self._collect_slice_params(item)
            tasks.append((file_path, params, config))
            self._items_by_path.setdefault(file_path, []).append(item)
            self.treeView.setValueFromRow(item, 'Status', 'queued')

        # Run the pool from a single helper thread so the UI stays responsive.
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.mainRoutines, tasks, config.worker_count)

    @handle_errors("executionPanel")
    def mainRoutines(self, tasks, worker_count=None):
        """
        Drive the ParallelExportCoordinator over the gathered tasks.

        Runs on a background thread. Results are marshalled back to the UI
        thread via ``root.after`` since tkinter is not thread-safe and the
        worker processes cannot touch the GUI.

        Returns
        -------
        None
        """
        def on_result(result):
            # Schedule the TreeView update on the main thread.
            self.root.after(0, self._apply_result_status, result)

        self.export_coordinator.run(
            tasks, worker_count=worker_count, progress_callback=on_result
        )

    def _apply_result_status(self, result):
        """Translate an ExportResult into a TreeView status (UI thread only)."""
        items = self._items_by_path.get(result.file_path)
        if not items:
            return
        item = items.pop(0)
        if result.error:
            self.treeView.setValueFromRow(item, 'Status', 'Error')
        elif result.failed_count > 0:
            self.treeView.setValueFromRow(
                item, 'Status', f'Done ({result.failed_count} failed)'
            )
        else:
            self.treeView.setValueFromRow(item, 'Status', 'Done')

    def breakAll(self):
        '''
        Stop the export cycle: cancel the coordinator (stops submitting new
        files) and the running service, and flag the queue loop to stop.

        Returns
        -------
        None.

        '''
        self.export_coordinator.cancel()
        self.export_service.cancel()
        self.running = 1

    def endProgram(self):
        '''
        terminates the programm.

        Returns
        -------
        None.

        '''
        #print('Exit - Nothing Happend!')
        self.endStatus = 1
        self.mainWin.quit()
        self.mainWin.destroy()

    def _collect_export_config(self) -> ExportConfig:
        """
        Gather current GUI state into an ExportConfig object.
        
        This method bridges the GUI widgets to the pure logic layer.
        """
        return export_config_from_gui_state(
            resize_state=self.globalSettingsFrame.getResizeState(),
            prefer_raw_state=self.globalSettingsFrame.prefRawBox.state(),
            advanced_filter_state=self.globalSettingsFrame.getAdvancedFilter(),
            export_format=self.globalSettingsFrame.getExpFormat(),
            averaging=self.globalSettingsFrame.averagingMenu.get(),
            tukey_size=self.globalSettingsFrame.getTukeyWinSize(),
            scale_state=self.globalSettingsFrame.ScaleBox.state(),
            scale_length=self.globalSettingsFrame.scaleEntry.get(),
            scale_font_size=self.globalSettingsFrame.scaleTextSizeEntry.get(),
        )

    def _collect_slice_params(self, item_id: str) -> SliceExportParams:
        """
        Gather TreeView row values into a SliceExportParams object.
        
        Args:
            item_id: The TreeView item identifier
            
        Returns:
            SliceExportParams with values from the TreeView row
        """
        return slice_export_params_from_treeview_row(
            path=self.treeView.getValueFromRow(item_id, column='Path'),
            name=self.treeView.getValueFromRow(item_id, 'Name'),
            first=self.treeView.getValueFromRow(item_id, 'First'),
            last=self.treeView.getValueFromRow(item_id, 'Last'),
            num_slices=self.treeView.getValueFromRow(item_id, 'NumSlices'),
            slice_dir=self.treeView.getValueFromRow(item_id, 'Img. Slice Dir.'),
            db_min=self.treeView.getValueFromRow(item_id, column='dB min'),
            db_max=self.treeView.getValueFromRow(item_id, column='dB max'),
            refr_ind=self.treeView.getValueFromRow(item_id, 'Refr. Ind.'),
            dispersion=self.customSettingsFrame.getDispersion(),
        )