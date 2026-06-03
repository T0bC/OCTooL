# -*- coding: utf-8 -*-
"""
Created on Tue Feb 23 14:58:13 2021

@author: Tobias Meissner
"""
import tkinter as tk
from tkinter import ttk
from utils.app_context import AppContext
from utils.status_bar import StatusBar
from app.view.rexview.tree_view_panel import treeViewPanel as table
from app.view.rexview.pick_files_panel import pickFilesPanel as pickFile
from app.view.rexview.global_settings_panel import globalSettingsPanel as globalSettings
from app.view.rexview.custom_settings_panel import customSettingsPanel as customSettings
from app.view.rexview.image_panel import imagePanel as imagePanel
from app.view.rexview.execution_panel import executionPanel as execution

def addContent(self, frame):
    self.rexViewTabFrame = frame
    self.context.root = self.rexViewTabFrame
    self.context.main_win = self.mainWin

    self.attach_status_bar(self.context)


    # Column configuration: col 0 (settings) fixed, col 1 (tree/image) expands
    self.rexViewTabFrame.columnconfigure(0, weight=0)
    self.rexViewTabFrame.columnconfigure(1, weight=1)
    # Row configuration: only row 5 (image viewer) expands vertically
    self.rexViewTabFrame.rowconfigure(0, weight=0)  # pickFrame - fixed height
    self.rexViewTabFrame.rowconfigure(1, weight=0)  # glblSttngsFrame - fixed height
    self.rexViewTabFrame.rowconfigure(4, weight=0)  # cstmSttngsFrame - fixed height
    self.rexViewTabFrame.rowconfigure(5, weight=1)  # imgFrame - expands vertically
    self.rexViewTabFrame.rowconfigure(9, weight=0)  # excFrame - fixed height

    # Create and register frames
    self.treeFrame = ttk.LabelFrame(self.rexViewTabFrame, text='Queue', relief=tk.RIDGE)
    self.treeFrame.grid(row=0, column=1, rowspan=5, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("tree", self.treeFrame)

    self.pickFrame = ttk.LabelFrame(self.rexViewTabFrame, text='Select File(s)', relief=tk.RIDGE)
    self.pickFrame.grid(row=0, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("pick_files", self.pickFrame)

    self.glblSttngsFrame = ttk.LabelFrame(self.rexViewTabFrame, text='Global Settings', relief=tk.RIDGE)
    self.glblSttngsFrame.grid(row=1, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("global_settings", self.glblSttngsFrame)

    self.cstmSttngsFrame = ttk.LabelFrame(self.rexViewTabFrame, text='Settings adjustable for each sample', relief=tk.RIDGE)
    self.cstmSttngsFrame.grid(row=4, column=0, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("custom_settings", self.cstmSttngsFrame)

    self.imgFrame = ttk.LabelFrame(self.rexViewTabFrame, text='Image Viewer', relief=tk.RIDGE)
    self.imgFrame.grid(row=5, column=0, rowspan=4, columnspan=2, sticky=tk.E + tk.W + tk.N + tk.S)
    self.context.register_frame("rex_image", self.imgFrame)

    self.excFrame = ttk.LabelFrame(self.rexViewTabFrame, text='Execution', relief=tk.RIDGE)
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
    self.context.register_panel("rex_image", self.imgPanel)

    self.excPanel = execution(self.context)
    self.context.register_panel("execution", self.excPanel)