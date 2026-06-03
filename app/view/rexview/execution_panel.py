#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
from concurrent import futures
from pathlib import Path
from utils import oct_functions as octF
from scipy import ndimage
from PIL import Image
from utils.tool_tip import Tooltip
import gc
import traceback
from utils.error_handler import handle_errors

# Import refactored logic components
from app.logic.rexview import ExportConfig, SliceExportParams, ExportProgress, ExportService
from app.logic.shared import OCTMetadata


# %% To Prevent GUI Freezing during a long loop or function we need to set up
# threads.
#threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)

class executionPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("execution")
        self.treeView = self.context.get_panel("tree")
        self.imageFrame = self.context.get_panel("image")
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
        # create a thread to keep UI responsive
        threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)
        threadPoolExecutor.submit(self.mainRoutines)

    @handle_errors("executionPanel")
    def mainRoutines(self):
        """
        Processes each item in the TreeView:
        - Unzips OCT data and reads header
        - Parses metadata and determines export parameters
        - Loads and processes raw or processed image data
        - Extracts slices and optionally adds scalebar
        - Saves the result with embedded metadata

        Returns
        -------
        None
        """
        for item in enumerate(self.treeView.getChildren()):
            if self.running == 1:
                break

            # Read file path and metadata
            self.file = self.treeView.getValueFromRow(item[1], column='Path')
            self.archive = octF.unzipOCTData(self.file)
            self.xmlContent = octF.readXMLContent(self.archive, 'Header.xml', 'xml')
            self.treeView.setValueFromRow(item[1], 'Status', 'loading')
            self.xmlDict = octF.getXMLAttributes(self.xmlContent)
            self.expNumber = self.xmlDict['expNumber']
            self.imgSliceDir = self.treeView.getValueFromRow(item[1], 'Img. Slice Dir.')

            # Create export directory
            self.exportPath = Path(f"{self.expNumber:02d}_{self.treeView.getValueFromRow(item[1],'Name')}_"
                                   f"{self.treeView.getValueFromRow(item[1],'NumSlices')}_Slices_{self.imgSliceDir}")
            Path(self.file).parent.joinpath(self.exportPath).mkdir(parents=True, exist_ok=True)

            # Collect config and params using existing helpers
            config = self._collect_export_config()
            params = self._collect_slice_params(item[1])

            # Use ExportService for preparation
            metadata = OCTMetadata.from_xml_dict(self.xmlDict)
            prep = self.export_service.prepare_export(params, config, metadata)

            # Use prepared values
            self.selectedSliceNumber = prep['selected_slices']
            self.slicesToLoadAndProcess = prep['slices_to_load']
            self.selDataType = prep['sel_data_type']

            # Callback to update GUI status
            def update_status(index):
                self.treeView.setValueFromRow(item[1], 'Status', str(index))

            # Use ExportService for image loading
            self.imgStack = self.export_service.load_image_stack(
                archive=self.archive,
                metadata=metadata,
                params=params,
                config=config,
                slices_to_load=self.slicesToLoadAndProcess,
                sel_data_type=self.selDataType,
                progress_callback=update_status,
            )

            # Loop through selected slices and export using ExportService
            failed_count = 0
            for image in enumerate(self.selectedSliceNumber):
                try:
                    if self.running == 1:
                        break

                    # Use ExportService for slice processing
                    self.finImg = self.export_service.process_slice(
                        img_stack=self.imgStack,
                        slice_idx=image[0],
                        image_idx=image[1],
                        params=params,
                        config=config,
                        metadata=metadata,
                    )

                    # Use ExportService for DPI calculation
                    self.dpi = self.export_service.calculate_dpi(self.finImg, params, metadata)

                    # Use ExportService for EXIF metadata
                    self.exif = self.export_service.add_exif_metadata(self.finImg, metadata)

                    # Use ExportService for filename generation
                    export_name = self.export_service.generate_export_filename(
                        params, config, metadata, image[1], image[0]
                    )
                    export_path = Path(self.file).parent / self.exportPath / export_name

                    # Use ExportService for saving
                    self.export_service.export_single_slice(self.finImg, export_path, self.dpi, self.exif)

                    self.treeView.setValueFromRow(item[1], 'Status', f"exp: {image[0]+1}")
                    gc.collect()
                except Exception:
                    failed_count += 1
                    traceback.print_exc()
                    continue  # Continue processing other images

            # Use ExportService for video image export
            self.export_service.export_video_image(
                archive=self.archive,
                metadata=metadata,
                params=params,
                export_dir=prep['export_dir'],
            )

            # Final cleanup per item
            if failed_count > 0:
                self.treeView.setValueFromRow(item[1], 'Status', f'Done ({failed_count} failed)')
            else:
                self.treeView.setValueFromRow(item[1], 'Status', 'Done')
            self.archive.close()
            gc.collect()

    def breakAll(self):
        '''
        Var for MainRoutine to break the export cycle.

        Returns
        -------
        None.

        '''
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

    def addExifToImage(self, finImg, xmlDict):
        '''
        Create an exif Object of Pil.Image module for additional Image Information

        Exif Tags
        https://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif.html
        https://github.com/python-pillow/Pillow/issues/4935

        Parameters
        ----------
        finImg : Pillow Image Object
            DESCRIPTION.
        xmlDict : dict
            Dictionary containing information about OCT File.

        Returns
        -------
        exif : Exif object of Pil.Image Module
            A Dictionary like object containig Exif information.

        '''
        exif = finImg.getexif()
        exif[0x9286] = 'Test' # UserComment


        return exif

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