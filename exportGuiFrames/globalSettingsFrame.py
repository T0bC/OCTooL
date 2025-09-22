#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from toolTip import Tooltip
#import octFunctions as octF

class globalSettingsPanel:
    def __init__(self, root, frame, treeView):
        self.root = root
        self.frame = frame
        self.treeView = treeView

        # %% Buttons and Checkboxes

        # %%Resizing the Image?
        self.resizeBox = ttk.Checkbutton(self.frame, text = 'Aspect Ratio')
        self.resizeBox.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.resizeBox.state(['!alternate'])
        self.resizeBox.state(['selected'])
        
        self.resizeToolTip = 'The pixels of an OCT scan are usually not isometric ' \
            'due to the standard acquisition parameters (x and y pixel size). ' \
            'A correction factor is calculated here so that the image does' \
            ' not look compressed or stretched, which makes the image appear natural.'
        Tooltip(self.resizeBox, text=self.resizeToolTip , wraplength=200)

        # %%prefer Raw Data
        self.prefRawBox = ttk.Checkbutton(self.frame, text='Prefer Raw')
        self.prefRawBox.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.prefRawBox.state(['!alternate'])
        self.prefRawBox.state(['selected'])
        
        self.prefRawToolTip = 'This is not yet implemented! If a scan was recorded '\
            ' as raw data and as spectral data, you can select here between ' \
            'processed and raw data export. '
        Tooltip(self.prefRawBox, text=self.prefRawToolTip , wraplength=200)
        
        # %%Advanced local filter
        self.advancedFilterBox = ttk.Checkbutton(self.frame, text = 'Local Filtering')
        self.advancedFilterBox.grid(row=0, column=2, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.advancedFilterBox.state(['!alternate'])
        self.advancedFilterBox.state(['!selected'])                              #disabled selected
        
        self.advancedFilterToolTip = 'Experimental: This filter can reduce ' \
            'noise if a raw scan is available. The filter operates in 32bit color' \
            'space and takes advantage of the "speckle" property of OCT. '\
            'It detects strong deviations of a pixel from the mean gray value of the '\
            'surrounding pixels and corrects this in a kind of median smoothing with a '\
            'predefined box kernel size. Since this is done by iterating over a B-scan ' \
            'columns and rows, this correction can take some time.'

        Tooltip(self.advancedFilterBox, text=self.advancedFilterToolTip , wraplength=200)
            
        # %%File Format
        
        self.exportFormatLabel = ttk.Label(self.frame, text = 'Exp. Format:')
        self.exportFormatLabel.grid(row = 0, column= 3, sticky= tk.E + tk.W)
  
        self.expFormatMenuToolTip = 'Export format: *.png results in a smaller file size. *.tiff '\
            'is ideal for postprocessing.'
        Tooltip(self.exportFormatLabel, text=self.expFormatMenuToolTip , wraplength=200)
        
        self.expFormatMenu = ttk.Combobox(self.frame, values = ['.png','.tiff'],
                                          width = 5, state = 'readonly')
        self.expFormatMenu.current(1)
        self.expFormatMenu.grid(row=0, column=4, sticky=tk.E, pady=3)

        Tooltip(self.expFormatMenu, text=self.expFormatMenuToolTip , wraplength=200)

        # %%Averaging method
        self.averagingLabel = ttk.Label(self.frame, text='Averaging:')
        self.averagingLabel.grid(row=1, column=0, sticky=tk.W, pady=3)
        
        self.averagingLabelToolTip = 'If A-scan averaging was activated during the recording,'\
            ' you can select here how the A-scans are averaged. "Coherent" results '\
            'in a signal-intensive image, whereas "Incoherent" leads to a noise-reduced image.'
        Tooltip(self.averagingLabel, text=self.averagingLabelToolTip , wraplength=200)
        
        self.averagingMenu = ttk.Combobox(self.frame, values = ['none','incoherent', 'coherent'],
                                          width = 10, state = 'readonly')
        self.averagingMenu.current(2)
        self.averagingMenu.grid(row=1, column=1, sticky=tk.W, pady=3)
        

        Tooltip(self.averagingMenu, text=self.averagingLabelToolTip , wraplength=200)

        # %%Tukey window size
        self.tukeyWinLabel = ttk.Label(self.frame, text='Apodization Win.:')
        self.tukeyWinLabel.grid(row=1, column=2, sticky=tk.W, pady=3)
        
        self.tukeyWinLabelToolTip = 'The size of the apodisation window determines '\
            ' how the raw data is filtered to show contrast differences. '\
            'The higher the value, the "sharper" the contrast edges can be displayed. '\
            'The steepness of a Tukey window is set here.'
        Tooltip(self.tukeyWinLabel, text=self.tukeyWinLabelToolTip , wraplength=200)
        
        self.tukeyWinSize = ttk.Combobox(self.frame, values=['0', '0.3', '0.5', '0.7', '0.9', '1'],
                                         width = 5, state = 'readonly')
        self.tukeyWinSize.current(4)
        self.tukeyWinSize.grid(row=1, column=3, sticky=tk.W, pady=3)
        
        Tooltip(self.tukeyWinSize, text=self.tukeyWinLabelToolTip, wraplength=200)

        # %% Add Scale to Image?
        self.ScaleBox = ttk.Checkbutton(self.frame, text = 'Draw Scale')
        self.ScaleBox.grid(row=2, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.ScaleBox.state(['!alternate'])
        self.ScaleBox.state(['selected'])
        
        self.scaleToolTip = 'Insert a scale to the right corner of the image. ' \
            'Choose Scale length and text size according to your needs. '
        Tooltip(self.ScaleBox, text=self.scaleToolTip , wraplength=200)
        
        # Scale length
        self.scaleLenghtLabel = ttk.Label(self.frame, text='Scale length [\u00B5m]:')
        self.scaleLenghtLabel.grid(row=2, column=1, sticky=tk.W, pady=3)
        
        self.scaleEntry = ttk.Entry(self.frame, width=6)
        self.scaleEntry.insert(0, '500')
        self.scaleEntry.grid(row=2, column=2, sticky=tk.E+tk.W, pady=3)
        
        self.scaleEntryToolTip = 'Insert a number here. Most common are 250, 500, 1000. '       
        Tooltip(self.scaleEntry, text=self.scaleEntryToolTip , wraplength=200)

        # Text Size Scale
        self.scaleTextSizeLabel = ttk.Label(self.frame, text='Text Size [pt]:')
        self.scaleTextSizeLabel.grid(row=2, column=3, sticky=tk.W, pady=3)
        
        self.scaleTextSizeEntry = ttk.Entry(self.frame, width=3)
        self.scaleTextSizeEntry.insert(0, '30')
        self.scaleTextSizeEntry.grid(row=2, column=4, sticky=tk.W + tk.E, pady=3)
        
        self.scaleTextSizeToolTip = 'Insert a number for text size here. e.g. 24 '       
        Tooltip(self.scaleTextSizeEntry, text=self.scaleTextSizeToolTip , wraplength=200)
        # %% Test  
        #self.testButton = tk.Button(self.frame, text="Test Funktion",
        #                            command=self.getDispersion())
        #self.testButton.grid(row=10,column=1, sticky=tk.E, pady=3)

    # %% Functions
    def getExpFormat(self)-> str:
        '''
        Returns the chosen export format

        Returns
        -------
        str
            '.png', '.tiff'.

        '''
        return self.expFormatMenu.get()

    def getAdvancedFilter(self)-> str:
        '''
        Returns state of Checkbox.

        Returns
        -------
        str
            'selected', 'alternate', 'disabled'.

        '''

        if len(self.advancedFilterBox.state()) < 1:
            self.filterState = 'None'
        else:
           self.filterState = self.advancedFilterBox.state()[0]

        return self.filterState    

    def getResizeState(self)-> str:
        '''
        Returns state of Checkbox.

        Returns
        -------
        str
            'selected', 'alternate', 'disabled'.

        '''

        if len(self.resizeBox.state()) < 1:
            self.resState = 'None'
        else:
           self.resState = self.resizeBox.state()[0]

        return self.resState

    def getAverageState(self)-> int:
        '''
        Returns the current state of the averaging method.

        Returns
        -------
        int
            State: 'none, 'incoherent', 'coherent'.

        '''
        return self.averagingMenu.get()

    def getPrefRawState(self)-> str:
        '''
        Returns state of prefere Raw Data Checkbox

        Returns
        -------
        str
            'selected', 'alternate', 'disabled'.

        '''
        return self.prefRawBox.state()
    
      
    def getTukeyWinSize(self)-> str:
        '''
        Returns the chosen Tukey windows size

        Returns
        -------
        str
            '0', '0.3', '0.5'....

        '''
        return self.tukeyWinSize.get()