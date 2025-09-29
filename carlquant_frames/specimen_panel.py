# -*- coding: utf-8 -*-
"""
Created on Fri Sep 26 14:49:04 2025

@author: meissnerto
"""

from tksheet import Sheet
from utils.error_handler import handle_errors

class specimenPanel:
    @handle_errors("specimenPanel.__init__")
    def __init__(self, context):
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("carl_specimen")

        self.headers = ['SPECIMEN_ID', 'SLICES', 'REGIONS', 'STATE']
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
        self.sheet.enable_bindings("single_select", "cell_select")
        self.sheet.extra_bindings("cell_select", func=self.on_row_selected)
        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

    @handle_errors("specimenPanel.on_row_selected")
    def on_row_selected(self, event):
        row_index = self.sheet.get_currently_selected()[0]
        specimen_id = self.sheet.get_cell_data(row_index, 0)
        specimen_data = self.context.specimen_data.get(specimen_id)

        if specimen_data:
            # Set current specimen in context
            self.context.current_specimen_id = specimen_id

            # Trigger image display in viewer panel
            viewer_panel = self.context.get_panel("carl_image")
            viewer_panel.display_image(0)  # Show first slice

            # Trigger results loading
            results_panel = self.context.get_panel("carl_results")
            results_panel.load_results_for(specimen_id)

            # Update status
            specimen_data.status = "displayed"
            self.sheet.set_cell_data(row_index, 3, "displayed")

            # Highlight selected row
            self.sheet.highlight_rows(rows="all", bg="white", fg="black", redraw=False)
            self.sheet.highlight_rows(rows=[row_index], bg="#ffd966", fg="black", redraw=True)

