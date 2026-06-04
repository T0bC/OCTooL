# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 11:24:40 2025

@author: Tobias Meissner
"""

from app.view.shared.error_handler import handle_errors
from tksheet import Sheet
from app.logic.annolyze.display_service import DisplayService
from app.view.shared import dialogs

class resultsPanel:
    @handle_errors("ResultsPanel.__init__")
    def __init__(self, context) -> None:
        """
        Initialize the ResultsPanel with static and dynamic column setup.

        Args:
            context: context manager that hold every panel and frame
        """
        self.context = context
        self.root = context.root
        self.frame = context.get_frame("results")
        self.img_frame = context.get_frame("anno_image")
        self.load_frame = context.get_frame("load")
        self.display_service = DisplayService()

        self.static_col_names = ['SPECIMEN_NAME', 'SLICE', 'OPERATOR', 'MEASUREMENT', 'SYSTEM', 'DATE_TIME']
        self.dynamic_col_specs: list[tuple[str, str]] = []  # List of (col_name, color)
        self.dynamic_insert_index = 2  # Insert after 'SLICE'

        self._setup_sheet()

    @handle_errors("ResultsPanel._setup_sheet")
    def _setup_sheet(self) -> None:
        """
        Set up the tksheet widget with initial configuration.
        """

        STATIC_BG_COLOR = "#2b2b2b"

        self.sheet = Sheet(
            self.frame,
            headers=self.static_col_names.copy(),
            show_table=True,
            show_top_left=True,
            show_row_index=True,
            show_header=True,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            width=800,
            height=180,
            empty_horizontal=0,
            empty_vertical=50
        )

        self.sheet.enable_bindings(
            "copy", "delete", "right_click_popup_menu", "single_select"
        )

        self.sheet.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._set_column_widths()

        font_color = self.choose_font_color(STATIC_BG_COLOR)
        static_indices = list(range(len(self.static_col_names)))

        self.sheet.highlight_columns(
            columns=static_indices,
            bg=STATIC_BG_COLOR,
            fg=font_color
        )

        self.sheet.highlight_rows(
            rows=list(range(self.sheet.total_rows())),
            bg=STATIC_BG_COLOR,
            fg=font_color
        )

    @handle_errors("ResultsPanel.reset_table")
    def reset_table(self):
        self.sheet.set_sheet_data([[]])  # Clear all data
        self.dynamic_col_specs.clear()
        self.sheet.headers(self.static_col_names.copy())
        self._set_column_widths()

        font_color = self.choose_font_color("#2b2b2b")
        static_indices = list(range(len(self.static_col_names)))

        self.sheet.highlight_columns(columns=static_indices, bg="#2b2b2b", fg=font_color)
        self.sheet.highlight_rows(rows=[], bg="#2b2b2b", fg=font_color)


    @handle_errors("ResultsPanel._set_column_widths")
    def _set_column_widths(self) -> None:
        """ Set column widths based on header length. """
        column_names = self.sheet.headers()

        for i, header in enumerate(column_names):
            width = self._calculate_column_width(header)
            self.sheet.column_width(i, width=width)

        self.sheet.refresh()

    def _calculate_column_width(self, header: str) -> int:
        """Calculate column width based on header length (delegates to DisplayService)."""
        return self.display_service.calculate_column_width(header)

    @handle_errors("ResultsPanel.add_dynamic_column")
    def add_dynamic_column(self, col_name: str, color: str, keyBind: str) -> None:
        """
        Add a dynamic column to the sheet if it doesn't already exist and the keyBind is unique.

        Args:
            col_name (str): Name of the column to add.
            color (str): Background color for the column.
            keyBind (str): Key binding associated with the column.
        """

        existing_names = [name for name, _ in self.dynamic_col_specs]
        if col_name in existing_names or col_name in self.static_col_names:
            dialogs.show_warning(
                self.root,
                "Duplicate Column",
                f"The column '{col_name}' already exists in the table."
            )
            return

        # Check for duplicate keyBind
        if keyBind and keyBind.lower() != "none":
            for existing_col, _, existing_key in getattr(self, "dynamic_col_specs_full", []):
                if keyBind == existing_key:
                    dialogs.show_warning(
                        self.root,
                        "Duplicate Key Binding",
                        f"The key binding '{keyBind}' is already assigned to column '{existing_col}'. Please choose a unique key."
                    )
                    return


        # Insert the column
        self.sheet.insert_column(
            column=None,
            idx=self.dynamic_insert_index,
            fill=True,
            undo=True,
            emit_event=False,
            redraw=False
        )

        # Set header name
        column_names = self.sheet.headers()
        column_names[self.dynamic_insert_index] = col_name
        self.sheet.headers(column_names)

        font_color = self.choose_font_color(color)

        # Highlight column
        self.sheet.highlight_columns(
            columns=[self.dynamic_insert_index],
            bg=color,
            fg=font_color
        )

        # Track column
        self.dynamic_col_specs.append((col_name, color))
        if not hasattr(self, "dynamic_col_specs_full"):
            self.dynamic_col_specs_full = []
        self.dynamic_col_specs_full.append((col_name, color, keyBind))

        # Remove placeholder row if present
        if self.sheet.total_rows() > 0:
            self.sheet.delete_row(rows=0)

        # Set all column widths at once
        self._set_column_widths()

        # Update insert index for next column
        self.dynamic_insert_index += 1



    @handle_errors("ResultsPanel.remove_last_dynamic_column")
    def remove_last_dynamic_column(self):
        """
        Remove the most recently added dynamic column from the sheet.

        Returns:
            str | None: Name of the removed column, or None if no dynamic column exists.
        """
        if not self.dynamic_col_specs:
            self.context.status_bar.update("No dynamic columns to remove.", level="success")
            return None

        last_col_name, _ = self.dynamic_col_specs.pop()
        column_names = self.sheet.headers()

        # Remove from dynamic_col_specs_full
        if hasattr(self, "dynamic_col_specs_full"):
            self.dynamic_col_specs_full = [
                spec for spec in self.dynamic_col_specs_full if spec[0] != last_col_name
            ]


        if last_col_name in column_names:
            col_index = column_names.index(last_col_name)
            self.sheet.delete_column(col_index)
            self.dynamic_insert_index -= 1
            return last_col_name
        else:
            self.context.status_bar.update(f"Column: {last_col_name} not found in headers.", level="warning")
            return None


    @handle_errors("ResultsPanel.populate_sample_data")
    def populate_sample_data(self) -> None:
        """
        Populate the sheet with sample static data.
        """
        sample_data = [
            ["Specimen A", "1", "Alice", "Length", "System X", "2023-01-01 10:00"],
            ["Specimen B", "2", "Bob", "Width", "System Y", "2023-01-02 11:00"],
            ["Specimen C", "3", "Charlie", "Height", "System Z", "2023-01-03 12:00"]
        ]
        self.sheet.set_sheet_data(sample_data)

        self._set_column_widths()

    @handle_errors("ResultsPanel.update_cell")
    def update_cell(self, row_index: int, col_name: str, value: str) -> None:
        """
        Update a specific cell in the sheet.

        Args:
            row_index (int): Row index of the cell.
            col_name (str): Column name of the cell.
            value (str): New value to set.
        """
        column_names = self.sheet.headers()
        if col_name in column_names:
            col_index = column_names.index(col_name)
            self.sheet.set_cell_data(row_index, col_index, value)
        else:
            self.context.status_bar.update(f"Column: {col_name} not found.", level="error")


    def get_luminance(self, hex_color: str) -> float:
        return self.display_service.luminance(hex_color)

    def choose_font_color(self, bg_color: str) -> str:
        return self.display_service.choose_font_color(bg_color)


