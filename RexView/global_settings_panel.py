#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils.tool_tip import Tooltip
from app.logic.rexview.settings_service import SettingsService

class globalSettingsPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("global_settings")
        self._settings_service = SettingsService()

        # %% Buttons and Checkboxes

        # %%Resizing the Image?
        self.resizeBox = ttk.Checkbutton(self.frame,
                                         text = 'Aspect Ratio',
                                         bootstyle="success")
        self.resizeBox.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.resizeBox.state(['!alternate'])
        self.resizeBox.state(['selected'])

        self.resizeToolTip = 'The pixels of an OCT scan are usually not isometric ' \
            'due to the standard acquisition parameters (x and y pixel size). ' \
            'A correction factor is calculated here so that the image does' \
            ' not look compressed or stretched, which makes the image appear natural.'
        Tooltip(self.resizeBox, text=self.resizeToolTip , wraplength=200)

        # %%prefer Raw Data
        self.prefRawBox = ttk.Checkbutton(self.frame,
                                          text='Prefer Raw',
                                          bootstyle="info")
        self.prefRawBox.grid(row=0, column=1, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.prefRawBox.state(['!alternate'])
        self.prefRawBox.state(['selected'])

        self.prefRawToolTip = 'This is not yet implemented! If a scan was recorded '\
            ' as raw data and as spectral data, you can select here between ' \
            'processed and raw data export. '
        Tooltip(self.prefRawBox, text=self.prefRawToolTip , wraplength=200)

        # %%Advanced local filter
        self.advancedFilterBox = ttk.Checkbutton(self.frame,
                                                 text = 'Local Filtering',
                                                 bootstyle="secondary")
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

        self.exportFormatLabel = ttk.Label(self.frame,
                                           text = 'Exp. Format:')
        self.exportFormatLabel.grid(row = 0, column= 3, sticky= tk.E + tk.W)

        self.expFormatMenuToolTip = 'RexView format: *.png results in a smaller file size. *.tiff '\
            'is ideal for postprocessing.'
        Tooltip(self.exportFormatLabel, text=self.expFormatMenuToolTip , wraplength=200)

        self.expFormatMenu = ttk.Combobox(self.frame,
                                          values = ['.png','.tiff'],
                                          width = 5,
                                          state = 'readonly',
                                          bootstyle="success")
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

        self.averagingMenu = ttk.Combobox(self.frame,
                                          values = ['none','incoherent', 'coherent'],
                                          width = 10,
                                          state = 'readonly',
                                          bootstyle="info")
        self.averagingMenu.current(2)
        self.averagingMenu.grid(row=1, column=1, sticky=tk.W, pady=3)
        Tooltip(self.averagingMenu, text=self.averagingLabelToolTip , wraplength=200)

        # %%Tukey window size
        self.tukeyWinLabel = ttk.Label(self.frame, text='Apodization Win.:')
        self.tukeyWinLabel.grid(row=1, column=2, sticky=tk.W, pady=3)

        self.tukeyWinLabelToolTip = 'The pixels of an OCT scan are usually not isometric ' \
            'due to the standard acquisition parameters (x and y pixel size). ' \
            'A correction factor is calculated here so that the image does' \
            ' not look compressed or stretched, which makes the image appear natural.'
        Tooltip(self.tukeyWinLabel, text=self.tukeyWinLabelToolTip , wraplength=200)

        self.tukeyWinSize = ttk.Combobox(self.frame,
                                         values=['0', '0.3', '0.5', '0.7', '0.9', '1'],
                                         width = 5,
                                         state = 'readonly',
                                         bootstyle="info")
        self.tukeyWinSize.current(4)
        self.tukeyWinSize.grid(row=1, column=3, sticky=tk.W, pady=3)
        Tooltip(self.tukeyWinSize, text=self.tukeyWinLabelToolTip, wraplength=200)

        # %%Show no text error?
        self.errorBox = ttk.Checkbutton(self.frame, text = 'Show Error', bootstyle="danger")
        self.errorBox.grid(row=1, column=4, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.errorBox.state(['!alternate'])
        self.errorBox.state(['!selected'])

        self.errorToolTip = 'If no text file is supplied next to the OCT file, '\
            'an error message is displayed. '\
            'You can disable/enable this here. \n'\
            'It will suppress the error message'
        Tooltip(self.errorBox, text=self.errorToolTip , wraplength=200)

        # %% Add Scale to Image?
        self.ScaleBox = ttk.Checkbutton(self.frame,
                                        text = 'Draw Scale',
                                        bootstyle="success")
        self.ScaleBox.grid(row=2, column=0, sticky=tk.E + tk.W + tk.N + tk.S, pady=3)
        self.ScaleBox.state(['!alternate'])
        self.ScaleBox.state(['selected'])

        self.scaleToolTip = 'Insert a scale to the right corner of the image. ' \
            'Choose Scale length and text size according to your needs. '
        Tooltip(self.ScaleBox, text=self.scaleToolTip , wraplength=200)

        # Scale length
        self.scaleLenghtLabel = ttk.Label(self.frame,
                                          text='Scale length [\u00B5m]:')
        self.scaleLenghtLabel.grid(row=2, column=1, sticky=tk.W, pady=3)

        self.scaleEntry = ttk.Entry(self.frame,
                                    width=6,
                                    bootstyle="success")
        self.scaleEntry.insert(0, '500')
        self.scaleEntry.grid(row=2, column=2, sticky=tk.E+tk.W, pady=3)

        self.scaleEntryToolTip = 'Insert a number here. Most common are 250, 500, 1000. '
        Tooltip(self.scaleEntry, text=self.scaleEntryToolTip , wraplength=200)

        # Text Size Scale
        self.scaleTextSizeLabel = ttk.Label(self.frame, text='Text Size [pt]:')
        self.scaleTextSizeLabel.grid(row=2, column=3, sticky=tk.W, pady=3)

        self.scaleTextSizeEntry = ttk.Entry(self.frame,
                                            width=3,
                                            bootstyle="success")
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

    def getErrorState(self)-> str:
        '''
        Returns state of Checkbox.

        Returns
        -------
        str
            'selected', 'alternate', 'disabled'.

        '''

        if len(self.errorBox.state()) < 1:
            self.errorState = 'None'
        else:
           self.errorState = self.errorBox.state()[0]

        return self.errorState

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

    def getScaleState(self)-> tuple:
        '''
        Returns state of Scale Checkbox

        Returns
        -------
        tuple
            ('selected',) or ().

        '''
        return self.ScaleBox.state()

    def getScaleLength(self)-> str:
        '''
        Returns the scale length entry value

        Returns
        -------
        str
            Scale length in micrometers.

        '''
        return self.scaleEntry.get()

    def getScaleFontSize(self)-> str:
        '''
        Returns the scale font size entry value

        Returns
        -------
        str
            Font size in points.

        '''
        return self.scaleTextSizeEntry.get()

    def _collect_settings_config(self) -> dict:
        '''
        Collect current global settings state for SettingsConfig creation.

        Returns
        -------
        dict
            Dictionary with global settings values ready for SettingsConfig.from_gui_state().

        '''
        return {
            'resize_state': self.getResizeState(),
            'prefer_raw_state': self.getPrefRawState(),
            'advanced_filter_state': self.getAdvancedFilter(),
            'export_format': self.getExpFormat(),
            'averaging': self.getAverageState(),
            'tukey_size': self.getTukeyWinSize(),
            'error_state': self.getErrorState(),
            'scale_state': self.getScaleState(),
            'scale_length': self.getScaleLength(),
            'scale_font_size': self.getScaleFontSize(),
        }

    def get_defaults(self) -> dict:
        '''
        Get default settings values from SettingsService.

        Returns
        -------
        dict
            Dictionary with default settings values.

        '''
        return self._settings_service.DEFAULTS