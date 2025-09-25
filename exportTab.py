# -*- coding: utf-8 -*-
"""
Created on Tue Feb 23 14:58:13 2021

@author: Tobias Meissner
"""
import tkinter as tk
from tkinter import ttk
from utils.app_context import AppContext
from utils.status_bar import StatusBar
from export_frames.tree_view_panel import treeViewPanel as table
from export_frames.pick_files_panel import pickFilesPanel as pickFile
from export_frames.global_settings_panel import globalSettingsPanel as globalSettings
from export_frames.custom_settings_panel import customSettingsPanel as customSettings
from export_frames.image_panel import imagePanel as imagePanel
from export_frames.execution_panel import executionPanel as execution

def addContent(self, frame):
    self.exportTabFrame = frame
    self.context = self.context
    self.context.root = self.exportTabFrame
    self.context.main_win = self.mainWin

    self.attach_status_bar(self.context)


    self.exportTabFrame.columnconfigure(0, weight=0)
    self.exportTabFrame.columnconfigure(1, weight=1)
    self.exportTabFrame.rowconfigure(0, weight=0)
    self.exportTabFrame.rowconfigure(5, weight=1)

    # Create and register frames
    self.treeFrame = ttk.LabelFrame(self.exportTabFrame, text='Queue', relief=tk.RIDGE)
    self.treeFrame.grid(row=0, column=1, rowspan=5, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("tree", self.treeFrame)

    self.pickFrame = ttk.LabelFrame(self.exportTabFrame, text='Select File(s)', relief=tk.RIDGE)
    self.pickFrame.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("pick_files", self.pickFrame)

    self.glblSttngsFrame = ttk.LabelFrame(self.exportTabFrame, text='Global Settings', relief=tk.RIDGE)
    self.glblSttngsFrame.grid(row=1, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("global_settings", self.glblSttngsFrame)

    self.cstmSttngsFrame = ttk.LabelFrame(self.exportTabFrame, text='Settings adjustable for each sample', relief=tk.RIDGE)
    self.cstmSttngsFrame.grid(row=4, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("custom_settings", self.cstmSttngsFrame)

    self.imgFrame = ttk.LabelFrame(self.exportTabFrame, text='Data Viewer', relief=tk.RIDGE)
    self.imgFrame.grid(row=5, column=0, rowspan=4, columnspan=2, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("image", self.imgFrame)

    self.excFrame = ttk.LabelFrame(self.exportTabFrame, text='Execution', relief=tk.RIDGE)
    self.excFrame.grid(row=9, column=0, columnspan=2, sticky=tk.W + tk.E + tk.S)
    self.context.register_frame("execution", self.excFrame)

    # Create and register panels
    self.treePanel = table(self.context)
    self.context.register_panel("tree", self.treePanel)

    self.glblSttngsPanel = globalSettings(self.context)
    self.context.register_panel("global_settings", self.glblSttngsPanel)

    self.cstmSttngsPanel = customSettings(self.context)
    self.context.register_panel("custom_settings", self.cstmSttngsPanel)

    self.pickPanel = pickFile(self.context)
    self.context.register_panel("pick_files", self.pickPanel)

    self.imgPanel = imagePanel(self.context)
    self.context.register_panel("image", self.imgPanel)

    self.excPanel = execution(self.context)
    self.context.register_panel("execution", self.excPanel)