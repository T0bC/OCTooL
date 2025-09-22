# -*- coding: utf-8 -*-
"""
Created on Tue Feb 23 14:58:13 2021

@author: Tobias Meissner
"""
import tkinter as tk
from tkinter import ttk
#from exportGuiFrames.instructionFrame import instructionPanel as instructions
from exportGuiFrames.treeViewFrame import treeViewPanel as table
from exportGuiFrames.pickFilesFrame import pickFilesPanel as pickFile
from exportGuiFrames.globalSettingsFrame import globalSettingsPanel as globalSettings
from exportGuiFrames.customSettingsFrame import customSettingsPanel as customSettings
from exportGuiFrames.imageFrame import imagePanel as imagePanel
from exportGuiFrames.executionFrame import executionPanel as execution


def addContent(self, frame):
    self.exportTabFrame = frame

    self.exportTabFrame.columnconfigure(0, weight=0)
    self.exportTabFrame.columnconfigure(1, weight=1)
    self.exportTabFrame.rowconfigure(0, weight=0)
    self.exportTabFrame.rowconfigure(5, weight=1)


    # %% Create Frames for Content here

    # INSTRUCTIONS
    #self.instrFrame = ttk.LabelFrame(self.exportTabFrame, text="Instructions...", relief=tk.RIDGE)
    #self.instrFrame.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S)

    # TREEVIEW
    self.treeFrame = ttk.LabelFrame(self.exportTabFrame, text='Queue', relief=tk.RIDGE)
    self.treeFrame.grid(row=0, column=1, rowspan=5, sticky=tk.E + tk.W + tk.N + tk.S)
    self.treeFrame.columnconfigure(1, weight=1)
    self.treeFrame.rowconfigure(0, weight=1)

    # PICKFILES
    self.pickFrame = ttk.LabelFrame(self.exportTabFrame, text='Select File(s)', relief=tk.RIDGE)
    self.pickFrame.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S)

    # SETTINGS
    self.glblSttngsFrame = ttk.LabelFrame(self.exportTabFrame, text='Global Settings', relief=tk.RIDGE)
    self.glblSttngsFrame.grid(row=1, column=0, sticky=tk.E + tk.W + tk.N + tk.S)

    # SETTINGS
    self.cstmSttngsFrame = ttk.LabelFrame(self.exportTabFrame, text='Settings adjustable for each sample', relief=tk.RIDGE)
    self.cstmSttngsFrame.grid(row=4, column=0, sticky=tk.E + tk.W + tk.N + tk.S)

    # IMAGE
    self.imgFrame = ttk.LabelFrame(self.exportTabFrame, text='Data Viewer', relief=tk.RIDGE)
    self.imgFrame.grid(row=5, column=0, rowspan=4, columnspan=2, sticky=tk.E + tk.W + tk.N + tk.S)
    self.imgFrame.rowconfigure(1, weight=1)
    self.imgFrame.columnconfigure(0, weight=1)

    # EXECUTION
    self.excFrame = ttk.LabelFrame(self.exportTabFrame, text='Excecution', relief=tk.RIDGE)
    self.excFrame.grid(row=9, column=0, columnspan=2, sticky=tk.W + tk.E + tk.S)


# %% Fill Content Frames with widgets here
    # create content (Panel) inside the frames / Create Instances of each class
    #self.instrPanel = instructions(self.exportTabFrame, self.instrFrame)
    self.treePanel = table(self.exportTabFrame, self.treeFrame)
    self.glblSttngsPanel = globalSettings(self.exportTabFrame, self.glblSttngsFrame, self.treePanel)
    self.cstmSttngsPanel = customSettings(self.exportTabFrame, self.cstmSttngsFrame, self.treePanel, self.pickFrame)
    self.pickPanel = pickFile(self.exportTabFrame, self.pickFrame, self.treePanel, self.glblSttngsPanel)
    self.imgPanel = imagePanel(self.exportTabFrame, self.imgFrame, self.treePanel, self.glblSttngsPanel, self.cstmSttngsPanel, self.pickFrame)
    self.excPanel = execution(self.exportTabFrame, self.excFrame, self.treePanel, self.imgPanel, self.glblSttngsPanel, self.cstmSttngsPanel, self.mainWin)