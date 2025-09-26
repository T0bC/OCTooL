# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:23:35 2025

@author: meissnerto
"""

from tkinter import ttk
import tkinter as tk
from utils.tool_tip import Tooltip
from utils.error_handler import handle_errors

class settingsPanel:
    @handle_errors("settingsPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_settings")

        self.frame.columnconfigure(0, weight=1)

        # Dummy Checkboxes
        self.optionA = True
        self.optionB = True
        self.optionC = True

        self.checkA = ttk.Checkbutton(self.frame,
                                      text = '1',
                                      bootstyle="success")
        self.checkA.grid(row=0, column=0, sticky="w", pady=2)

        self.checkB = ttk.Checkbutton(self.frame,
                                      text = '2',
                                      bootstyle="success")
        self.checkB.grid(row=1, column=0, sticky="w", pady=2)

        self.checkC = ttk.Checkbutton(self.frame,
                                      text = '3',
                                      bootstyle="success")
        self.checkC.grid(row=2, column=0, sticky="w", pady=2)

        # Dummy Dropdown
        self.dropdownLabel = ttk.Label(self.frame, text="Select Mode:")
        self.dropdownLabel.grid(row=3, column=0, sticky="w", pady=(10, 2))

        self.modeVar = tk.StringVar()
        self.dropdown = ttk.Combobox(self.frame, textvariable=self.modeVar, state="readonly")
        self.dropdown['values'] = ["Mode 1", "Mode 2", "Mode 3"]
        self.dropdown.current(0)
        self.dropdown.grid(row=4, column=0, sticky="ew", pady=2)
