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

        self.style = Style(theme="darkly")
        
        # Create custom tab styles with different colors
        self._setup_tab_styles()


# %% Create custom colored tab system
        # Create container for custom tab system
        self.tabContainer = ttk.Frame(self.mainWin)
        self.tabContainer.grid(row = 0, column = 0, sticky = tk.E + tk.W + tk.N + tk.S)
        self.tabContainer.columnconfigure(0, weight=1)
        self.tabContainer.rowconfigure(1, weight=1)
        
        # Create custom tab bar with colored buttons
        self.tabBar = ttk.Frame(self.tabContainer)
        self.tabBar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        
        # Create colored tab buttons
        self.create_colored_tab_buttons()
        
        # Create content area (using notebook without visible tabs)
        self.tabParent = ttk.Notebook(self.tabContainer)
        self.tabParent.grid(row = 1, column = 0, sticky = tk.E + tk.W + tk.N + tk.S)
        
        # Hide the notebook tabs after creation
        self.tabParent.configure(style="Hidden.TNotebook")
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

        # %% Carl Quant
        self.carlQuantFrame = ttk.Frame(self.tabParent)
        self.tabParent.add(self.carlQuantFrame, text='CarlQuant')
        carl_quant.addContent(self, self.carlQuantFrame)

        # Apply custom styles to individual tabs after all tabs are created
        self._apply_tab_colors()

        self.mainWin.update_idletasks()  # Ensure layout is processed
        self.mainWin.deiconify()

    def _setup_tab_styles(self):
        """Setup custom styles for colored tab buttons."""
        # Hide the default notebook tabs completely by modifying the layout
        self.style.layout("Hidden.TNotebook", [
            ("Notebook.client", {"sticky": "nswe"})
        ])  # Only keep the client area, remove tab area
        
        # Alternative: Set tab height to 0
        self.style.configure(
            "Hidden.TNotebook.Tab",
            padding=[0, 0, 0, 0],  # No padding at all
            borderwidth=0,         # No border
            focuscolor="none",
            relief="flat"
        )
        
        # Make tabs invisible by setting their size to 0
        self.style.map(
            "Hidden.TNotebook.Tab",
            expand=[("selected", [0, 0, 0, 0])],  # No expansion
            background=[("selected", ""), ("active", ""), ("!active", "")],
            foreground=[("selected", ""), ("active", ""), ("!active", "")]
        )
        
        # Create colored button styles for each tab
        # Export tab - Blue/Primary
        self.style.configure(
            "Export.TButton",
            background=self.style.colors.primary,
            foreground="white",
            borderwidth=0,
            focuscolor="none",
            padding=[20, 10]
        )
        
        # Analyze tab - Green/Success  
        self.style.configure(
            "Analyze.TButton",
            background=self.style.colors.success,
            foreground="white", 
            borderwidth=0,
            focuscolor="none",
            padding=[20, 10]
        )
        
        # CarlQuant tab - Orange/Warning
        self.style.configure(
            "CarlQuant.TButton",
            background=self.style.colors.warning,
            foreground="white",
            borderwidth=0, 
            focuscolor="none",
            padding=[20, 10]
        )

    def create_colored_tab_buttons(self):
        """Create colored buttons that act as tabs."""
        self.tab_buttons = []
        self.current_tab = 0
        
        # Export button
        export_btn = ttk.Button(
            self.tabBar, 
            text="Export", #📊 
            style="Export.TButton",
            command=lambda: self.switch_tab(0),
            takefocus=False  # Prevent button from taking focus
        )
        export_btn.grid(row=0, column=0, padx=(0,2))
        self.tab_buttons.append(export_btn)
        
        # Analyze button  
        analyze_btn = ttk.Button(
            self.tabBar,
            text="Analyze", #🔬 
            style="Analyze.TButton",
            command=lambda: self.switch_tab(1),
            takefocus=False  # Prevent button from taking focus
        )
        analyze_btn.grid(row=0, column=1, padx=2)
        self.tab_buttons.append(analyze_btn)
        
        # CarlQuant button
        carlquant_btn = ttk.Button(
            self.tabBar,
            text="CarlQuant", #⚡ 
            style="CarlQuant.TButton", 
            command=lambda: self.switch_tab(2),
            takefocus=False  # Prevent button from taking focus
        )
        carlquant_btn.grid(row=0, column=2, padx=(2,0))
        self.tab_buttons.append(carlquant_btn)

    def switch_tab(self, tab_index):
        """Switch to the specified tab."""
        # Force the button to lose focus immediately
        self.mainWin.focus_set()
        
        # Switch to the tab
        self.tabParent.select(tab_index)
        self.current_tab = tab_index
        
        # Force an immediate update of the display
        self.tabParent.update_idletasks()
        
        # Update button appearances (optional: make selected button darker)
        for i, btn in enumerate(self.tab_buttons):
            # Remove focus from all buttons
            btn.state(['!pressed', '!active'])
            
            if i == tab_index:
                # Make selected button slightly darker
                if i == 0:  # Export
                    btn.configure(style="Export.TButton")
                elif i == 1:  # Analyze  
                    btn.configure(style="Analyze.TButton")
                elif i == 2:  # CarlQuant
                    btn.configure(style="CarlQuant.TButton")

    def _apply_tab_colors(self):
        """Apply the hidden style to notebook tabs."""
        # Hide the default notebook tabs since we're using custom buttons
        try:
            for i in range(self.tabParent.index("end")):
                self.tabParent.tab(i, text="")  # Remove text from hidden tabs
        except tk.TclError:
            pass

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
