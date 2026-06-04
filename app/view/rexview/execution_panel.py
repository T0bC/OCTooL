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
from app.logic.rexview import ExportConfig, SliceExportParams, ExportService


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
        To prevent GUII from freezing during a loop or time consuming function
        call, we need to set up threads.
        In this thread we call the mainRoutines.

        Returns
        -------
        None.

        '''
        #print('starting')
        self.running = 0
        self.export_service.reset()
        # create a thread to keep UI responsive
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.mainRoutines)

    @handle_errors("executionPanel")
    def mainRoutines(self):
        """
        Iterate the TreeView queue and delegate each row's export to
        ExportService.run_export(). This panel only does view work:
        gather widget state via the _collect_* collectors, call the
        service, and translate ExportProgress into TreeView status text.

        Returns
        -------
        None
        """
        for item in self.treeView.getChildren():
            if self.running == 1:
                break

            file_path = self.treeView.getValueFromRow(item, column='Path')
            config = self._collect_export_config()
            params = self._collect_slice_params(item)

            self.treeView.setValueFromRow(item, 'Status', 'loading')

            def progress_callback(progress, _item=item):
                # Translate ExportProgress -> TreeView status text.
                if progress.status.startswith('Loading: '):
                    self.treeView.setValueFromRow(
                        _item, 'Status', progress.status[len('Loading: '):]
                    )
                elif progress.total_slices:
                    self.treeView.setValueFromRow(
                        _item, 'Status', f"exp: {progress.current_slice}"
                    )

            exported_files = self.export_service.run_export(
                file_path, params, config, progress_callback=progress_callback
            )

            # Final status per item (preserve legacy text).
            if self.export_service.is_cancelled:
                self.treeView.setValueFromRow(item, 'Status', 'Done')
            else:
                failed_count = params.num_slices - len(exported_files)
                if failed_count > 0:
                    self.treeView.setValueFromRow(item, 'Status', f'Done ({failed_count} failed)')
                else:
                    self.treeView.setValueFromRow(item, 'Status', 'Done')

    def breakAll(self):
        '''
        Stop the export cycle: cancel the running service (breaks the
        per-slice loop) and flag the outer queue loop to stop.

        Returns
        -------
        None.

        '''
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
        return ExportConfig.from_gui_state(
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
        return SliceExportParams.from_treeview_row(
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