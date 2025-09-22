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
#from matplotlib import pylab as plt
from PIL import Image
from toolTip import Tooltip
import gc


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
                                     command=self.mainRoutine)
        self.executeBtn.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S)
        self.exportToolTip = "Start exporting of all entrys in queue."
        Tooltip(self.executeBtn, text=self.exportToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid(
            row=0, column=2, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)

        self.breakBtn = ttk.Button(self.frame, text='Cancel!', width=10,
                                   command=self.breakAll)
        self.breakBtn.grid(row=0, column=3, sticky=tk.E + tk.W + tk.N + tk.S)
        self.stoppToolTip = "Stopp export."
        Tooltip(self.breakBtn, text=self.stoppToolTip , wraplength=200)

        self.button_label = ttk.Label(self.frame, text='  ')
        self.button_label.grid(
            row=0, column=4, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)


        self.quitBtn = ttk.Button(self.frame, text='Quit!', width=10,
                                  command=self.endProgram)
        self.quitBtn.grid(row=0, column=5, sticky=tk.E + tk.W + tk.N + tk.S)
        self.quitToolTip = "Exits the application."
        Tooltip(self.quitBtn, text=self.quitToolTip , wraplength=200)
        
        # %%

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


    def mainRoutines(self):
        '''
        Iterates over the TreeView list. Extracts the path to the file.
        Processes the file and saves it into the Raw-Data Folder.

        Returns
        -------
        None.

        '''
        for item in enumerate(self.treeView.getChildren()):
            if self.running == 1:
                break
            
            
            
            self.file = self.treeView.getValueFromRow(item[1], column='Path')
            # Unzip Data and read XML Header to Buffer
            self.archive = octF.unzipOCTData(self.file)
            self.xmlContent = octF.readXMLContent(self.archive, 'Header.xml', 'xml')
            self.treeView.setValueFromRow(item[1], 'Status', 'loading')

            #  Get MetaInfo from XML File
            self.xmlDict = octF.getXMLAttributes(self.xmlContent)
            self.expNumber = self.xmlDict['expNumber']

            self.exportPath = Path(str(str(f'{self.expNumber:02d}') +
                                              '_' +
                                              str(self.treeView.getValueFromRow(item[1],'Name')) +
                                              '_' +
                                              str(self.treeView.getValueFromRow(item[1],'NumSlices')) +
                                              '_Slices'))
           
            #  Create Output Directory
            Path(Path(self.file).parent / self.exportPath).mkdir(parents=True,
                                                                 exist_ok=True)
            

            self.selectedSliceNumber = np.linspace(start=int(self.treeView.getValueFromRow(item[1],'First'))-1,
                                                    stop=int(self.treeView.getValueFromRow(item[1],'Last'))-1,
                                                    num=int(self.treeView.getValueFromRow(item[1],'NumSlices'))).astype(int)
            
            if (self.xmlDict['dataType'] == 'RawSpectraAndProcessedIntensity' and 
                self.globalSettingsFrame.prefRawBox.state() == ('selected',) or
                self.xmlDict['dataType'] == 'RawSpectra'):
                for image in enumerate(self.selectedSliceNumber):
                    # break lopp if user hits cancel
                    if self.running == 1:
                        break
    
                    self.finImg = octF.createImageFromRaw(xmlDict=self.xmlDict,
                                                          archive=self.archive,
                                                          dBmin=int(self.treeView.getValueFromRow(item[1],column='dB min')),
                                                          dBmax=int(self.treeView.getValueFromRow(item[1],column='dB max')),
                                                          selDataType='Raw',
                                                          averaging=self.globalSettingsFrame.averagingMenu.get(),
                                                          spectral=image[1],
                                                          prefRaw=self.globalSettingsFrame.getPrefRawState()[0],
                                                          resizeState=self.globalSettingsFrame.getResizeState(),
                                                          tukeySize=float(self.globalSettingsFrame.getTukeyWinSize()),
                                                          advancedFilter=self.globalSettingsFrame.getAdvancedFilter(),
                                                          dispersion=self.customSettingsFrame.getDispersion())
    
                    # Save image
                    if self.globalSettingsFrame.ScaleBox.state() == ('selected',):
                        self.finImg = octF.insertScale(img = Image.fromarray(self.finImg), 
                                                       scaleSize = int(self.globalSettingsFrame.scaleEntry.get()),
                                                       xmlDict = self.xmlDict,
                                                       fontSize = int(self.globalSettingsFrame.scaleTextSizeEntry.get()))
                    else:
                        self.finImg = Image.fromarray(self.finImg)
                    
                    self.exif = self.addExifToImage(self.finImg, self.xmlDict)
                    
                    self.dpi = (round(np.shape(self.finImg)[1] / (self.xmlDict['imgSizemmX'] )), 
                                round(np.shape(self.finImg)[0] / (self.xmlDict['imgSizemmZ'] )))
                    
                    self.finImg.save(Path(Path(self.file).parent / self.exportPath / str(self.treeView.getValueFromRow(item[1],'Name') +
                                                                                   '_' + str(self.xmlDict['expNumber']) +
                                                                                   '_#' +
                                                                                   str(image[1]+1) +
                                                                                   '_' +
                                                                                   str(f'{image[0]+1:04d}') +
                                                                                   self.globalSettingsFrame.getExpFormat())),
                                     dpi = self.dpi,
                                     resolution_unit = 3,
                                     #x_resolution = 1,
                                     #y_resolution = 1,
                                     exif = self.exif)
                    self.treeView.setValueFromRow(item[1], 'Status', str(image[0]+1))
                    gc.collect()
            else:
                self.img = octF.createImageFromRaw(xmlDict=self.xmlDict,
                                                   archive=self.archive,
                                                   dBmin=int(self.treeView.getValueFromRow(item[1],column='dB min')),
                                                   dBmax=int(self.treeView.getValueFromRow(item[1],column='dB max')),
                                                   selDataType='Processed',
                                                   averaging=self.globalSettingsFrame.averagingMenu.get(),
                                                   spectral=0,
                                                   prefRaw='Processed',
                                                   resizeState=self.globalSettingsFrame.getResizeState(),
                                                   tukeySize=float(self.globalSettingsFrame.getTukeyWinSize()),
                                                   advancedFilter=self.globalSettingsFrame.getAdvancedFilter(),
                                                   dispersion=self.customSettingsFrame.getDispersion())
                for image in enumerate(self.selectedSliceNumber):
                    # break lopp if user hits cancel
                    if self.running == 1:
                        break
                    
                    if self.globalSettingsFrame.ScaleBox.state() == ('selected',):
                        self.finImg = octF.insertScale(img = Image.fromarray(self.img[:,:,image[1]]), 
                                                       scaleSize = int(self.globalSettingsFrame.scaleEntry.get()),
                                                       xmlDict = self.xmlDict,
                                                       fontSize = int(self.globalSettingsFrame.scaleTextSizeEntry.get()))
                    else:
                        self.finImg = Image.fromarray(self.img[:,:,image[1]])                    
                    
                    self.exif = self.addExifToImage(self.finImg, self.xmlDict)    
                    
                    self.dpi = (round(np.shape(self.finImg)[1] / (self.xmlDict['imgSizemmX'] )), 
                                round(np.shape(self.finImg)[0] / (self.xmlDict['imgSizemmZ'] )))
                    
                    self.finImg.save(Path(Path(self.file).parent / self.exportPath / str(self.treeView.getValueFromRow(item[1],'Name') +
                                                                                   '_' + str(self.xmlDict['expNumber']) +
                                                                                   '_#' +
                                                                                   str(image[1]+1) +
                                                                                   '_' +
                                                                                   str(f'{image[0]+1:04d}') +
                                                                                   self.globalSettingsFrame.getExpFormat())),
                                     dpi = self.dpi,
                                     resolution_unit = 3,
                                    # x_resolution = 1,
                                    # y_resolution = 1,
                                     exif = self.exif)
                    self.treeView.setValueFromRow(item[1], 'Status', str(image[0]+1))                      
            
            # Close Archive before EXIT (free up Memory)
            self.treeView.setValueFromRow(item[1], 'Status', str('Done'))
            self.archive.close()
            gc.collect()
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