#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 18:54:40 2020

@author: Tobias Meißner tobias.meissner@medizin.uni-leipzig.de
"""

import tkinter as tk
from tkinter import ttk
#from ttkthemes import ThemedStyle
from ttkbootstrap import Style
import exportTab
import analyzingTab
import carl_quant
from utils.app_context import AppContext
from utils.status_bar import StatusBar


class MainGui:
    def __init__(self):

        self.mainWin = tk.Tk()
        self.mainWin.withdraw()

        self.context = AppContext()
        self.context.root = self.mainWin

        self.version = ' [v. 1.1.0 - 20250807]'
        self.mainWin.title(str('OCTexVIEW' + self.version))
        self.pathToFolder = None
        self.mainWin['padx'] = 5
        self.mainWin['pady'] = 5

        # Initialize Menubar to window
        self.menubar = tk.Menu(self.mainWin)
        self.helpmenu = tk.Menu(self.menubar)
        self.helpmenu.add_command(label = 'Help', command=self.onHelp)
        self.helpmenu.add_command(label = 'About', command=self.onAbout)

        self.menubar.add_cascade(label="Help", menu=self.helpmenu)
        self.mainWin.config(menu=self.menubar)

        # seetings for resizing of the window
        self.mainWin.columnconfigure(0, weight = 1)
        self.mainWin.rowconfigure(0, weight = 1)
        self.mainWin.rowconfigure(1, weight = 0)

        # set a custom icon
        self.mainWin.iconbitmap("icons/thumb_4.ico")

        #self.style = Style(theme="darkly")


# %% Create exportTabFrame Here
        # initialize a tabbed main frame
        self.tabParent = ttk.Notebook(self.mainWin)
        self.tabParent.grid(row = 0, column = 0, sticky = tk.E + tk.W + tk.N + tk.S)
        # make the window resizeable
        self.tabParent.columnconfigure(0, weight = 1)
        self.tabParent.rowconfigure(0, weight = 1)

        # Shared status bar container
        self.statusFrame = ttk.Frame(self.mainWin)
        self.statusFrame.grid(row = 1, column = 0, sticky = tk.E + tk.W, pady = (5, 0))
        self.statusFrame.columnconfigure(0, weight = 1)

        self.statusBar = StatusBar(self.statusFrame)
        self.statusBar.frame.grid(row = 0, column = 0, sticky = "ew")

        # %% EXPORT TAB
        # create a frame holding the contents for the tab
        self.exportTabFrame = ttk.Frame(self.tabParent)
        self.tabParent.add(self.exportTabFrame, text = 'Export')
        # Fill the tab with content defined in exportTab.py
        exportTab.addContent(self, self.exportTabFrame)


        # %% ADDITIONAL FRAME 1
        self.analyzingFrame = ttk.Frame(self.tabParent)
        self.tabParent.add(self.analyzingFrame, text = 'Analyze')
        analyzingTab.addContent(self, self.analyzingFrame)

        self.mainWin.update_idletasks()  # Ensure layout is processed
        self.mainWin.deiconify()


        # %% Carl Quant
        self.carlQuantFrame = ttk.Frame(self.tabParent)
        self.tabParent.add(self.carlQuantFrame, text='CarlQuant')
        carl_quant.addContent(self, self.carlQuantFrame)


    def start(self):
        self.mainWin.mainloop() #start monitoring and updating the GUI

    def onHelp(self):

        self.helpMessage = \
            '1. Choose a folder with Thorlabs OCT files. All Files inside this\n   folder are populated into a list.\n' \
            '   You can choose single files as well!\n \n' \
            '2. You can select an item in the list to adapt the export range,  aequidistant slices or dispersion.\n\n' \
            '3. You can display a given slice with the "Show" button. Adjust the slice with the slider\n\n' \
            '4. Adjust Dyn. Range to you liking for a single file or for all\n   files. Check if the dispersion needs to be adjusted.\n\n' \
            '5. Click on "Export" to start the export. The outputfolder is\n    found in the original directory of the OCT File'
        tk.messagebox.askquestion(title = 'Help', message = self.helpMessage)

    def onAbout(self):

        self.aboutMassage = \
            str('OCTexVIEW' + self.version) + '\n\n' \
                'Developed by \nTobias Meißner [1], \n' \
                'Maximilian Bemmann [1] \n' \
                'with contribution from \n' \
                'Jonas Golde [2]\n\n' \
                '1: Universität Leipzig - Poliklinik für Zahnerhaltung und Parodontologie\n' \
                '2: Technische Universität Dresden - Medizinische Fakultät Carl Gustav Carus - Klinisches Sensoring und Monitoring\n\n' \
                'Error Reports to: tobias.meissner@medizin.uni-leipzig.de'

        tk.messagebox.showinfo(title = 'Help', message = self.aboutMassage)

    def attach_status_bar(self, context):
        """Attach the shared status bar to a given context."""
        if hasattr(self, "statusBar") and self.statusBar:
            self.statusBar.attach_context(context)
        else:
            raise RuntimeError("StatusBar not initialized in MainGui")
