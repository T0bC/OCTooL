# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:49:04 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tksheet import Sheet
from utils.error_handler import handle_errors

class specimenPanel:
    @handle_errors("specimenPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_specimen")

        self.headers = ['SPECIMEN_ID', 'SOURCE', 'DATE', 'STATUS']
        self._setup_sheet()

    def _setup_sheet(self):
        self.sheet = Sheet(
            self.frame,
            headers=self.headers,
            show_table=True,
            show_row_index=True,
            show_header=True,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            width=400,
            height=180
        )
        self.sheet.enable_bindings("copy", "delete", "single_select")
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
