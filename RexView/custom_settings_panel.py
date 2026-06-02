#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:55:08 2020

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import ttk
from utils import oct_functions as octF
from utils.tool_tip import Tooltip

class customSettingsPanel:
    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("custom_settings")
        self.treeView = self.context.get_panel("tree")

        # %% Buttons and Checkboxes

        # %%First and last Slice to export
        self.boundLabelToolTip = 'Here you can manually enter the first and last slice '\
            ' to be exported. Afterwards, the values can be transferred to all entries'\
            ' in the queue or only to the currently selected one.'

        self.boundLabel1 = ttk.Label(self.frame, text='Exp. Range:')
        self.boundLabel1.grid(row=3, column=0, sticky=tk.W, pady=3)

        Tooltip(self.boundLabel1, text=self.boundLabelToolTip , wraplength=200)

        self.firstEntry = ttk.Entry(self.frame, width=4, bootstyle="success")
        self.firstEntry.insert(0, 'First')
        self.firstEntry.grid(row=3, column=1, sticky=tk.W, pady=3)
        Tooltip(self.firstEntry, text=self.boundLabelToolTip , wraplength=200)

        self.lastEntry = ttk.Entry(self.frame, width=4, bootstyle="success")
        self.lastEntry.insert(0, 'Last')
        self.lastEntry.grid(row=3, column=1, sticky=tk.E, pady=3)
        Tooltip(self.lastEntry, text=self.boundLabelToolTip , wraplength=200)

        self.addNmbrsButton = ttk.Button(self.frame, text='Selection',
                                        command = lambda: self.treeView.addSliceToQueue(firstEntry = self.firstEntry.get(),
                                                                                        lastEntry = self.lastEntry.get(),
                                                                                        resetState =  False),
                                        bootstyle="secondary")
        self.addNmbrsButton.grid(row=3, column=2, sticky=tk.E + tk.W, pady=3)
        Tooltip(self.addNmbrsButton, text=self.boundLabelToolTip , wraplength=200)

        self.addAllRangeButton = ttk.Button(self.frame, text='Set All',
                                           command = lambda: self.treeView.addToMultipleColsnRows(colNames = ['First', 'Last', 'NumSlices'],
                                                                                                  values = [self.firstEntry.get(),
                                                                                                            self.lastEntry.get(),
                                                                                                            str(int(self.lastEntry.get()) - int(self.firstEntry.get()) +1)]),
                                           bootstyle="secondary")
        self.addAllRangeButton.grid(row=3, column=3, sticky=tk.E + tk.W, pady=3)
        Tooltip(self.addAllRangeButton, text=self.boundLabelToolTip , wraplength=200)

        self.resetNumSlicesButton = ttk.Button(self.frame, text='Reset Sel',
                                              command = lambda: self.treeView.addSliceToQueue(firstEntry = 1,
                                                                                              lastEntry = octF.getXMLvalue(self.treeView.getValue('Path'), 'dimY'),
                                                                                              resetState = True),
                                              bootstyle="secondary")
        self.resetNumSlicesButton.grid(row=3, column=4, sticky=tk.E + tk.W, pady=3)

        self.resetNumSlicesToolTip = 'Sets the first level to 1 and the last level to the last available level.'
        Tooltip(self.resetNumSlicesButton, text=self.resetNumSlicesToolTip , wraplength=200)

        # %%Equidistant Slices
        self.resetNumSlicesToolTip = 'To export evenly distributed slices from a scan,'\
            ' the number can be entered here and transferred to all or one entry in the queue.'

        self.equidistLabel = ttk.Label(self.frame, text='Equidist. slices:')
        self.equidistLabel.grid(row=4, column=0,  sticky=tk.W, pady=3)
        Tooltip(self.equidistLabel, text=self.resetNumSlicesToolTip , wraplength=200)

        self.numSlicesEntry = ttk.Entry(self.frame,
                                        width=4,
                                        bootstyle="success")
        self.numSlicesEntry.insert(0, '25')
        self.numSlicesEntry.grid(row=4, column=1, sticky=tk.W, pady=3)
        Tooltip(self.numSlicesEntry, text=self.resetNumSlicesToolTip , wraplength=200)

        self.addCurrSlicesButton = ttk.Button(self.frame, text='Selection',
                                             command = lambda: self.treeView.addequiDistToQueue(self.numSlicesEntry.get(), False),
                                             bootstyle="secondary")
        self.addCurrSlicesButton.grid(row=4, column=2, sticky=tk.E + tk.W, pady=3)
        Tooltip(self.addCurrSlicesButton, text=self.resetNumSlicesToolTip , wraplength=200)

        self.addAllSlicesButton = ttk.Button(self.frame, text='Set All',
                                            command = lambda: self.treeView.addequiDistToQueue(self.numSlicesEntry.get(), True),
                                            bootstyle="secondary")
        self.addAllSlicesButton.grid(row=4, column=3, sticky= tk.E + tk.W, pady=3)
        Tooltip(self.addAllSlicesButton, text=self.resetNumSlicesToolTip , wraplength=200)

        self.resetCurSlicesButton = ttk.Button(self.frame, text='Reset Sel',
                                              command = lambda: self.treeView.setValueFromRow(item = self.treeView.getFocus(),
                                                                                              column = 'NumSlices',
                                                                                              value = int(self.treeView.getValueFromRow(self.treeView.getFocus(), 'Last')) -
                                                                                                      int(self.treeView.getValueFromRow(self.treeView.getFocus(), 'First')) + 1),
                                              bootstyle="secondary")
        self.resetCurSlicesButton.grid(row=4, column=4, sticky=tk.E, pady=3)
        self.resetNumSlicesToolTip = 'Resets the value to "all slices".'
        Tooltip(self.resetCurSlicesButton, text=self.resetNumSlicesToolTip , wraplength=200)

        # %%Dezibel

        self.dynRangeLabelToolTip = 'Roughly speaking, the dynamic range indicates the '\
            'range between the darkest and lightest grey values. A kind of contrast adjustment' \
            ' takes place, so to speak. In the concrete case, the signal-to-noise ratio is defined here.'

        self.dynRangeLabel = ttk.Label(self.frame, text='Dyn. Range [dB]')
        self.dynRangeLabel.grid(row = 5, column = 0, sticky=tk.W, pady=3)
        Tooltip(self.dynRangeLabel, text=self.dynRangeLabelToolTip , wraplength=200)

        # we need to define the value variable for the scale output label befor creating the scale
        self.valueScale = tk.StringVar()

        self.scaleMdB = ttk.Scale(self.frame, from_=0, to=50, orient='horizontal',
                                  command = self.setDBValue,
                                  bootstyle="success")

        self.scaleMdB.grid(row = 5, column = 1, sticky=tk.E + tk.W)
        self.lowerdbScaleToolTip = "Lower dB-Value"
        Tooltip(self.scaleMdB, text=self.lowerdbScaleToolTip , wraplength=200)

        self.scaleAdB = ttk.Scale(self.frame, from_=50, to=120, orient='horizontal',
                                  command = self.setDBValue,
                                  bootstyle="success")
        self.scaleAdB.grid(row = 5, column = 2, sticky=tk.E + tk.W)
        self.upperdbScaleToolTip = "Upper dB-Value"
        Tooltip(self.scaleAdB, text=self.upperdbScaleToolTip , wraplength=200)

        # set the scale standards after the scale is created
        self.scaleAdB.set(100)
        self.scaleMdB.set(30)

        self.valueScale = tk.StringVar()
        self.valueScale.set(str(str(int(self.scaleMdB.get())) + " - " + str(int(self.scaleAdB.get()))))
        self.scaleValue = ttk.Label(self.frame, textvariable=self.valueScale)
        self.scaleValue.grid(row=5, column = 3, sticky=tk.E + tk.W)
        self.bothdbScaleToolTip = "Lower and upper dB-Values"
        Tooltip(self.scaleValue, text=self.bothdbScaleToolTip , wraplength=200)

        self.addDBAllSlicesButton = ttk.Button(self.frame, text='Set All',
                                               command = lambda: self.treeView.addToMultipleColsnRows(colNames = ['dB min', 'dB max'],
                                                                                                      values = [int(self.scaleMdB.get()), int(self.scaleAdB.get())]),
                                               bootstyle="secondary")
        self.addDBAllSlicesButton.grid(row=5, column=4, sticky=tk.E, pady=3)
        self.setDBToolTip = "Set the value to all entrys in the queue."
        Tooltip(self.addDBAllSlicesButton, text=self.setDBToolTip , wraplength=200)

        # %% Autocorelation Compensation  Dispersion

        self.dispersionToolTip = '-100 for 1500nm OCT \n+20 for 1310 nm OCT. \nAdjust to your projekt!\n\n'\
            'When using broadband light sources for OCT, dispersion effects '\
            'inevitably occur due to the optics in the interferometer and the samples themselves.'\
            ' The spectral components propagate at different speeds due to the different optical '\
            'path lengths and produce a spectral interferogram with a non-uniform period. If the '\
            'dispersion is not compensated, this leads to the broadening of the point spread '\
            'function of the Fourier transform. To achieve the best possible resolution, a '\
            'dispersion correction must be carried out. This can be achieved '\
            'either by appropriate dispersion elements in the interferometer arms or numerically '\
            'by means of software. The latter is done here. The value used must be determined empirically.'

        self.dispersionMenu = ttk.Combobox(self.frame, values = ['Quadratic', 'None'],
                                           width = 10, state = 'readonly',
                                           bootstyle="primary")
        self.dispersionMenu.current(0)
        self.dispersionMenu.grid(row=6, column=0, sticky=tk.W, pady=3)
        Tooltip(self.dispersionMenu, text=self.dispersionToolTip , wraplength=200)

        self.dispVal = tk.IntVar()
        self.dispUnit = tk.StringVar()

        self.dispEntry = ttk.Entry(self.frame,
                                   width=4,
                                   bootstyle="success")
        self.dispEntry.insert(0, '-100')
        self.dispEntry.grid(row=6, column=1, sticky=tk.W, pady=3)
        self.dispValueToolTip = "Enter value between -100 and +100 here!"
        Tooltip(self.dispEntry, text=self.dispValueToolTip , wraplength=200)

        self.dispUnit.set('A.U.')
        self.dispValLabel2 = ttk.Label(self.frame, textvariable=self.dispUnit)
        self.dispValLabel2.grid(row=6, column=1, sticky=tk.E)

        self.addCurrDispButton = ttk.Button(self.frame, text='Selection',
                                             command = lambda: self.treeView.setValue('Disp. Coeff', str(self.dispEntry.get())),
                                             bootstyle="secondary")
        self.addCurrDispButton.grid(row=6, column=2, sticky=tk.E + tk.W, pady=3)
        self.dipsSelToolTip = "Add value to selection!"
        Tooltip(self.addCurrDispButton, text=self.dipsSelToolTip , wraplength=200)

        self.addAllDispButton = ttk.Button(self.frame, text='Set All',
                                            command = lambda: self.treeView.addToMultipleColsnRows([str('Disp. Coeff')], [str(self.dispEntry.get())]),
                                            bootstyle="secondary")
        self.addAllDispButton.grid(row=6, column=3, sticky=tk.E + tk.W, pady=3)
        self.dipsAllToolTip = "Add value to all in queue!"
        Tooltip(self.addAllDispButton, text=self.dipsAllToolTip , wraplength=200)

        self.resetCurDispButton = ttk.Button(self.frame, text='Reset Sel',
                                              command = lambda: self.treeView.addToMultipleColsnRows([('Disp. Coeff')], [str(-100)]),
                                              bootstyle="secondary")
        self.resetCurDispButton.grid(row=6, column=4, sticky=tk.E + tk.W, pady=3)
        self.dipsResToolTip = "Reset values to -100."
        Tooltip(self.resetCurDispButton, text=self.dipsResToolTip , wraplength=200)

        # %% RexView direction
        self.expDirLabelToolTip = 'Define the image slice direction here. First character is always the X axis (width) and second always the y axis (height) of the resulting image.'

        self.expDirLabel = ttk.Label(self.frame, text='Image Slice Direction')
        self.expDirLabel.grid(row = 7, column = 0, sticky=tk.W, pady=3)
        Tooltip(self.expDirLabel, text=self.expDirLabelToolTip , wraplength=200)

        self.expDirToolTip = 'XZ: 2D projection along the XZ plane.\n' \
            'YZ: 2D projection along the YZ plane (standard).\n' \
            'XY: 2D projection along the XY plane.'

        self.expDirMenu = ttk.Combobox(self.frame, values = ['XZ', 'YZ', 'XY'],
                                           width = 5, state = 'readonly',
                                           bootstyle="success")

        self.expDirMenu.current(0)
        self.expDirMenu.grid(row=7, column=1, sticky=tk.W, pady=3)
        Tooltip(self.expDirMenu, text=self.expDirToolTip , wraplength=200)

        self.addCurrExpDirButton = ttk.Button(self.frame, text='Selection',
                                             command = lambda: self.treeView.setImgSliceDirectionAndUpdateLastSliceInTreeview(str(self.expDirMenu.get())),
                                             bootstyle="secondary")
        self.addCurrExpDirButton.grid(row=7, column=2, sticky=tk.E + tk.W, pady=3)
        self.expDirSelToolTip = "Add value to selection!"
        Tooltip(self.addCurrExpDirButton, text=self.expDirSelToolTip , wraplength=200)

        self.addAllExpDirButton = ttk.Button(self.frame, text='Set All',
                                            command = lambda: self.treeView.updateImgSliceDirectionForAllEntries(str(self.expDirMenu.get())),
                                            bootstyle="secondary")
        self.addAllExpDirButton.grid(row=7, column=3, sticky=tk.E + tk.W, pady=3)
        self.expDirAllToolTip = "Add value to all in queue!"
        Tooltip(self.addAllExpDirButton, text=self.expDirAllToolTip , wraplength=200)

        # %% Refractive Index
        self.refractiveIndexLabelTooltip = 'Defines how much the image is stretched or compressed. A value of 1 shows true surface dimensions; higher values  distort the surface but retain approximate depth accuracy.'

        self.refractiveIndexLabel = ttk.Label(self.frame, text='Refractive Index')
        self.refractiveIndexLabel.grid(row=8, column=0, sticky=tk.W, pady=3)
        Tooltip(self.refractiveIndexLabel, text=self.refractiveIndexLabelTooltip, wraplength=200)

        self.refractiveIndexEntryTooltip = 'Enter the refractive index (e.g. 1.0). Values >1 stretch the surface while maintaining depth cues. Use with caution for samples with varying indices.'

        self.refractiveIndexEntry = ttk.Entry(self.frame,
                                              width=4,
                                              bootstyle="success")
        self.refractiveIndexEntry.insert(0, 1)
        self.refractiveIndexEntry.grid(row=8, column=1, sticky=tk.W, pady=3)
        Tooltip(self.refractiveIndexEntry, text=self.refractiveIndexEntryTooltip, wraplength=200)

        self.selectionButtonTooltip = "Add value to selection!"

        self.selectionButton = ttk.Button(self.frame, text='Selection',
                                          command=lambda: self.treeView.setValue('Refr. Ind.', str(self.dispEntry.get())),
                                          bootstyle="secondary")
        self.selectionButton.grid(row=8, column=2, sticky=tk.E + tk.W, pady=3)
        Tooltip(self.selectionButton, text=self.selectionButtonTooltip, wraplength=200)

        self.setAllButtonTooltip = "Add value to all in queue!"

        self.setAllButton = ttk.Button(self.frame, text='Set All',
                                       command=lambda: self.treeView.addToMultipleColsnRows(['Refr. Ind.'], [str(self.dispEntry.get())]),
                                       bootstyle="secondary")
        self.setAllButton.grid(row=8, column=3, sticky=tk.E + tk.W, pady=3)
        Tooltip(self.setAllButton, text=self.setAllButtonTooltip, wraplength=200)


    # %% Functions
    def setDBValue(self, value: int):
        '''
        Sets the chosen dB - Value for min or max dB

        Parameters ,
        ----------
        value : (int)
            current state (position) of scale.

        Returns
        -------
        None.

        '''
        self.treeView.setdBVal(int(self.scaleMdB.get()), int(self.scaleAdB.get()))
        self.valueScale.set(str(str(int(self.scaleMdB.get())) + " - " + str(int(self.scaleAdB.get()))))


    def getEbenenState(self)-> str:
        '''
        Returns state of box weather to export 25 slices

        Returns
        -------
        str
            'selected', 'alternate', 'disabled'.

        '''
        return self.expBox.state()

    def getDispersion(self):
        '''
        Returns a tuple with all information about the chosen dispersion settings.

        Returns
        -------
        Bool
            Returns 'selected' if Box is checked.
        Str
            Returns a String of the Method ('Quadric').
        int
            Returns the position of the scale, which is the correction value.

        '''
        return (self.dispersionMenu.get(), self.dispEntry.get()) #self.dispersionBox.state()[0],