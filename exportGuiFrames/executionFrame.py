#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
from concurrent import futures
from pathlib import Path
import octFunctions as octF
from scipy import ndimage
from PIL import Image
from toolTip import Tooltip
import gc
import traceback
from tkinter import messagebox

def show_error_popup(title="Unexpected Error", exception=None):
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    error_message = f"{str(exception)}\n\nTraceback:\n{traceback.format_exc()}"
    messagebox.showerror(title, error_message)
    root.destroy()

def catch_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            show_error_popup(f"Error in {func.__name__}", e)
    return wrapper


# %% To Prevent GUI Freezing during a long loop or function we need to set up
# threads.
#threadPoolExecutor = futures.ThreadPoolExecutor(max_workers=1)

class executionPanel:
    def __init__(self, root, frame, treeView, imgFrame, globalSettingsFrame, customSettingsFrame, mainWin):
        self.root = root
        self.frame = frame
        self.treeView = treeView
        self.imageFrame = imgFrame
        self.globalSettingsFrame = globalSettingsFrame
        self.customSettingsFrame = customSettingsFrame
        self.mainWin = mainWin

        self.executeBtn = ttk.Button(self.frame, text='Export!', width=10,
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
    @catch_errors
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

    @catch_errors
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

            # Determine slices to process
            self.selectedSliceNumber = np.linspace(
                int(self.treeView.getValueFromRow(item[1],'First')) - 1,
                int(self.treeView.getValueFromRow(item[1],'Last')) - 1,
                int(self.treeView.getValueFromRow(item[1],'NumSlices'))
            ).astype(int)

            if self.imgSliceDir == 'XZ':
                self.slicesToLoadAndProcess = self.selectedSliceNumber
            else:
                self.slicesToLoadAndProcess = np.linspace(0, int(self.xmlDict['dimY']) - 1, int(self.xmlDict['dimY'])).astype(int)

            # Decide between raw or processed data
            if (self.xmlDict['dataType'] == 'RawSpectraAndProcessedIntensity' and
                self.globalSettingsFrame.prefRawBox.state() == ('selected',)) or \
                self.xmlDict['dataType'] == 'RawSpectra':
                self.selDataType = 'Raw'
            else:
                self.selDataType = 'Processed'

            # Callback to update GUI status
            def update_status(index):
                self.treeView.setValueFromRow(item[1], 'Status', str(index))

            # Generate image stack
            self.imgStack = octF.createImageFromRaw(
                xmlDict=self.xmlDict,
                archive=self.archive,
                dBmin=int(self.treeView.getValueFromRow(item[1], column='dB min')),
                dBmax=int(self.treeView.getValueFromRow(item[1], column='dB max')),
                selDataType=self.selDataType,
                averaging=self.globalSettingsFrame.averagingMenu.get(),
                spectral=self.slicesToLoadAndProcess,
                prefRaw=self.globalSettingsFrame.getPrefRawState()[0],
                tukeySize=float(self.globalSettingsFrame.getTukeyWinSize()),
                advancedFilter=self.globalSettingsFrame.getAdvancedFilter(),
                dispersion=self.customSettingsFrame.getDispersion(),
                update_callback=update_status
            )

            # Loop through selected slices and export
            for image in enumerate(self.selectedSliceNumber):
                try:
                    if self.running == 1:
                        break

                    # resize or add scale bar
                    self.finImg =  self.prepareImageSlice(image=image, item=item)

                    # Add EXIF metadata
                    self.exif = self.addExifToImage(self.finImg, self.xmlDict)

                    # Calculate DPI from spatial dimensions
                    if self.imgSliceDir == 'XZ':
                        self.dpi = (round(self.finImg.size[0] / self.xmlDict['imgSizemmX']),
                                    round(self.finImg.size[1] / self.xmlDict['imgSizemmZ']))
                    elif self.imgSliceDir == 'YZ':
                        self.dpi = (round(self.finImg.size[0] / self.xmlDict['imgSizemmY']),
                                    round(self.finImg.size[1] / self.xmlDict['imgSizemmZ']))
                    else:
                        self.dpi = (round(self.finImg.size[0] / self.xmlDict['imgSizemmY']),
                                    round(self.finImg.size[1] / self.xmlDict['imgSizemmX']))

                    # Save image with DPI and metadata
                    export_name = f"{self.treeView.getValueFromRow(item[1],'Name')}_{self.xmlDict['expNumber']}_#" \
                                  f"{image[1] + 1}_{image[0] + 1:04d}{self.globalSettingsFrame.getExpFormat()}"
                    export_path = Path(self.file).parent / self.exportPath / export_name

                    # in some cases image is in float
                    self.finImg = self.finImg.convert(mode = 'L')

                    self.finImg.save(export_path, dpi=self.dpi, resolution_unit=3, exif=self.exif)

                    self.treeView.setValueFromRow(item[1], 'Status', f"exp: {image[0]+1}")
                    gc.collect()
                except Exception:
                    print(traceback.format_exc())

            # export video image
            try:
                self.videoImage = Image.fromarray(
                    octF.createVideoImageFromRaw(
                        xmlDict=self.xmlDict,
                        archive=self.archive
                        )
                    )

                export_name = f"{self.treeView.getValueFromRow(item[1],'Name')}_{self.xmlDict['expNumber']}.jpg"
                export_path_vid = Path(self.file).parent / self.exportPath.parent / export_name
                self.videoImage.save(export_path_vid, format='JPEG', resolution_unit=3)
            except Exception:
                    print(traceback.format_exc())

            # Final cleanup per item
            self.treeView.setValueFromRow(item[1], 'Status', 'Done')
            self.archive.close()
            gc.collect()

    @catch_errors
    def prepareImageSlice(self, image, item):
        """
        Prepares a 2D image slice from a 2D or 3D image stack, applies resizing,
        refractive index correction, and optionally adds a scale bar.

        Parameters:
            image (tuple): Tuple of slice indices (e.g., (i, j))
            item (tuple): TreeView item reference for metadata lookup

        Returns:
            PIL.Image: Final processed image with optional scale bar
        """

        # Determine if image stack is 2D or 3D
        self.imgStack = np.squeeze(self.imgStack)
        is2D = self.imgStack.ndim == 2

        # Choose correct index depending on direction
        self.imageToExport = image[0] if self.imgSliceDir == 'XZ' else image[1]

        # Extract image slice
        if is2D:
            self.img = Image.fromarray(self.imgStack)
        else:
            if self.imgSliceDir == 'XZ':
                self.img = Image.fromarray(self.imgStack[self.imageToExport, :, :])
            elif self.imgSliceDir == 'YZ':
                self.img = np.transpose(Image.fromarray(self.imgStack[:, :, self.imageToExport]))
            elif self.imgSliceDir == 'XY':
                self.img = Image.fromarray(self.imgStack[:, self.imageToExport, :])

        # Resize if enabled
        if self.globalSettingsFrame.getResizeState() == 'selected':

            resizeX = self.xmlDict.get('imgResizeFactorX', 1)
            resizeY = self.xmlDict.get('imgResizeFactorY', 1)

            if self.imgSliceDir == 'XZ':
                self.img = ndimage.zoom(self.img, zoom=(1, resizeX), order=0)
            elif self.imgSliceDir == 'YZ':
                self.img = ndimage.zoom(self.img, zoom=(1, resizeY), order=0)
            elif self.imgSliceDir == 'XY' or is2D:
                self.img = ndimage.zoom(self.img, zoom=(resizeY, resizeX), order=0)

        # Apply refractive index correction
        refrInd = float(self.treeView.getValueFromRow(item[1], 'Refr. Ind.'))
        if refrInd != 1:
            self.img = ndimage.zoom(self.img, zoom=(refrInd, 1), order=0)

        # Add scale bar if selected
        if self.globalSettingsFrame.ScaleBox.state() == ('selected',):
            self.finImg = octF.insertScale(
                img=Image.fromarray(self.img),
                scaleSize=int(self.globalSettingsFrame.scaleEntry.get()),
                xmlDict=self.xmlDict,
                fontSize=int(self.globalSettingsFrame.scaleTextSizeEntry.get()),
                imgSliceDir=self.imgSliceDir
            )
        else:
            self.finImg = Image.fromarray(self.img)

        return self.finImg


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