#!/usr/bin/env python3
"""
RexView Tree View Panel.

Export queue displayed as a tksheet table with columns for slice range, dB,
direction, refractive index, dispersion, and status. Only the parameter columns
are editable in place; rows are addressed through stable opaque IDs.

Key contents:
- treeViewPanel: tksheet panel managing the export queue.
- setMultipleValues / deleteEntry: Add and remove queue rows.
- getValue / setValue / getValueFromRow / setValueFromRow: Cell accessors (str values).
- getFocus / getChildren: Row ID of the current selection and of all rows.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
"""

from app.logic.rexview import QueueItem, QueueService
from app.logic.shared import oct_functions as octF
from app.view.rexview.gui_adapters import queue_item_from_treeview_values
from app.view.shared import dialogs
from app.view.shared.sheet_panel import BaseSheetPanel


class treeViewPanel(BaseSheetPanel):
    COLS = (
        "Nr.",
        "Name",
        "First",
        "Last",
        "dB min",
        "dB max",
        "NumSlices",
        "Refr. Ind.",
        "Disp. Coeff",
        "Img. Slice Dir.",
        "Data Type",
        "Status",
        "Path",
    )
    COL_WIDTHS = (25, 200, 50, 50, 50, 50, 63, 50, 70, 90, 70, 70, 35)
    EDITABLE_COLS = ("First", "Last", "dB min", "dB max", "NumSlices", "Refr. Ind.", "Disp. Coeff")

    def __init__(self, context):
        self.context = context
        self.root = self.context.root
        self.frame = self.context.get_frame("tree")

        # Initialize QueueService for business logic
        self._queue_service = QueueService()

        self.cols = self.COLS
        self._col = {name: i for i, name in enumerate(self.COLS)}

        # Stable opaque row IDs, parallel to the sheet rows (rows are plain
        # indices in tksheet and shift on delete). Never enable sorting, row
        # drag-move, row hiding or built-in row insert/delete on this sheet.
        self._row_ids: list[str] = []
        self._next_id = 0

        # No "delete" binding: the Delete key would clear cells. Rows are
        # removed through deleteEntry.
        self._build_sheet(
            self.frame,
            self.COLS,
            (
                "single_select",
                "row_select",
                "drag_select",
                "ctrl_select",
                "shift_select",
                "arrowkeys",
                "copy",
                "edit_cell",
                "column_width_resize",
            ),
            show_row_index=False,
            total_rows=0,  # a bare Sheet starts with 100 empty rows
        )
        self.sheet.set_column_widths(self.COL_WIDTHS)
        self.sheet.readonly_columns(
            [i for i, c in enumerate(self.COLS) if c not in self.EDITABLE_COLS], readonly=True
        )
        self.sheet.edit_validation(self._on_cell_edited)

    # %% Row IDs and cell primitives
    def _new_id(self) -> str:
        self._next_id += 1
        return f"R{self._next_id}"

    def _row_of(self, item_id) -> int | None:
        """Sheet row index of an ID, or None if the row was deleted."""
        try:
            return self._row_ids.index(item_id)
        except ValueError:
            return None

    def _get(self, item_id, column: str) -> str:
        row = self._row_of(item_id)
        return "" if row is None else str(self.sheet.get_cell_data(row, self._col[column]))

    def _set(self, item_id, column: str, value) -> None:
        row = self._row_of(item_id)
        if row is not None:
            self.sheet.set_cell_data(row, self._col[column], str(value))

    def _on_cell_edited(self, event):
        """Validation hook for in-place edits: report and store the value as str."""
        self.context.safe_status_update("Cell value updated.", level="info")
        return str(event.value)

    def _renumber(self) -> None:
        """Rewrite the "Nr." column as 1..n."""
        for i in range(len(self._row_ids)):
            self.sheet.set_cell_data(i, self._col["Nr."], str(i + 1), redraw=False)
        self.sheet.refresh()

    # %% deleteEntry
    def deleteEntry(self):
        """
        Deletes the current selection from the queue table

        Returns
        -------
        None.

        """
        rows = sorted(self.sheet.get_selected_rows(get_cells_as_rows=True))
        if not rows:
            return
        self.sheet.delete_rows(rows, undo=False, redraw=True)
        for row in reversed(rows):
            del self._row_ids[row]
        self.sheet.deselect("all")
        self.context.safe_status_update(f"Removed {len(rows)} item(s) from queue.", level="info")
        self._renumber()

    # addSliceToQueue
    def addSliceToQueue(self, firstEntry: int, lastEntry: int, resetState: bool):
        """
        Change the parameter for first and fast Slice in the queue table

        Parameters
        ----------
        firstEntry : int
            Value from user input field.
        lastEntry : int
            Value from user input field.
        resetStat : bool
            if resize button is used calcculate numOfSlices differently

        Returns
        -------
        None.

        """
        self.firstEntry = firstEntry
        self.lastEntry = lastEntry
        if not resetState:
            self.numOfSlices = int(lastEntry) - int(firstEntry)
        else:
            self.numOfSlices = int(lastEntry) - int(firstEntry) + 1

        focus = self.getFocus()
        self._set(focus, "First", self.firstEntry)
        self._set(focus, "Last", self.lastEntry)
        self._set(focus, "NumSlices", self.numOfSlices)
        self.context.safe_status_update("Slice range updated.", level="info")

    # setdBVal

    def setdBVal(self, mdB: int, adB: int):
        """
        Sets the dBValue according to the sliders.

        Parameters
        ----------
        mdB : int
            Current value (state) of scale.
        adB : int
            Current value (state) of scale.

        Returns
        -------
        None.

        """
        self.scaleMdB = mdB
        self.scaleAdB = adB

        if not self.getFocus():
            pass
        else:
            self._set(self.getFocus(), "dB min", self.scaleMdB)
            self._set(self.getFocus(), "dB max", self.scaleAdB)
            self.context.safe_status_update("dB range updated.", level="info")

    def getChildren(self) -> list:
        """
        Returns a (ID) list of all entries in the queue table

        Returns: List of ID's'
        -------
        TYPE
            List.

        """
        return list(self._row_ids)

    def setValue(self, column: str, value: str):
        """
        Sets value in given row and column in the treeFrame

        Parameters
        ----------
        column : str
            Column name.
        value : str
            Value to be set.

        Returns
        -------
        None.

        """
        self._set(self.getFocus(), column, value)

    def getFocus(self) -> str:
        """
        Returns the ID of the currently selected row

        Returns
        -------
        str
            Row ID, or "" if nothing is selected.

        """
        sel = self.sheet.get_currently_selected()
        if not sel or sel.row is None or not 0 <= sel.row < len(self._row_ids):
            return ""
        return self._row_ids[sel.row]

    def getValue(self, column: int) -> str:
        """
        Returns the value of specified column

        Parameters
        ----------
        column : int
            column number 1st col = 0.

        Returns
        -------
        str:
            Value in Column as string .

        """
        return self._get(self.getFocus(), column)

    def getValueFromRow(self, item, column: int) -> str:
        """
        Returns from a given row (Child)

        Parameters
        ----------
        item : TYPE
            row number?.
        column : int
            column name.

        Returns
        -------
        str
            DESCRIPTION.

        """
        return self._get(item, column)

    def setValueFromRow(self, item, column: str, value: str):
        """
        Sets value in given row and column in the treeFrame

        Parameters
        ----------
        column : str
            Column name.
        value : str
            Value to be set.

        Returns
        -------
        None.

        """
        self._set(item, column, value)

    def setMultipleValues(self, tmpFileList: list):
        """
        Sets multiple Values from a given list into the treeView table

        Parameters
        ----------
        tmpFileList : list
            A list containing values generated by file/folder Picker.
                : i = increment (int)
                : name = name of file
                : first = first slice to be exportet (standard = 1)
                : last = last slice to be exportet (standard = end)
                : dB = Dezibel values (standard = 20 - 80)
                : status = status of export
                : path = Path to file

        Returns
        -------
        None.

        """

        rows = []
        start = len(self._row_ids)
        for i, (
            name,
            first,
            last,
            dBMin,
            dBMax,
            NumSlices,
            RefrInd,
            DispCoeff,
            imgSliceDir,
            dataType,
            status,
            path,
        ) in enumerate(tmpFileList, start=start + 1):
            values = (
                i,
                name,
                first,
                last,
                dBMin,
                dBMax,
                NumSlices,
                RefrInd,
                DispCoeff,
                imgSliceDir,
                dataType,
                status,
                path,
            )
            rows.append([str(v) for v in values])
        if not rows:
            return
        self.sheet.insert_rows(
            rows, idx=None, undo=False, create_selections=False, redraw=True
        )  # None appends
        self._row_ids.extend(self._new_id() for _ in rows)

    def _collect_queue_item_from_row(self, item_id) -> QueueItem:
        """
        Collect current row values into a QueueItem model.

        Parameters
        ----------
        item_id : str
            Row ID

        Returns
        -------
        QueueItem
            Model containing row data
        """
        return queue_item_from_treeview_values(
            name=self._get(item_id, "Name"),
            first=self._get(item_id, "First"),
            last=self._get(item_id, "Last"),
            db_min=self._get(item_id, "dB min"),
            db_max=self._get(item_id, "dB max"),
            num_slices=self._get(item_id, "NumSlices"),
            refr_ind=self._get(item_id, "Refr. Ind."),
            disp_coeff=self._get(item_id, "Disp. Coeff"),
            slice_dir=self._get(item_id, "Img. Slice Dir."),
            data_type=self._get(item_id, "Data Type"),
            status=self._get(item_id, "Status"),
            path=self._get(item_id, "Path"),
        )

    def addequiDistToQueue(self, numSlices: str, allFiles: bool):
        """
        Add equidistant Slice number to the queue table

        Parameters
        ----------
        numSlices : str
            Number of equidistant slices.
        allFiles : bool
            False = Set only to current selection
            True = Set to all loaded oct files.

        Returns
        -------
        None.

        """
        if not allFiles:
            first_slice = int(self.getValue(column="First"))
            last_slice = int(self.getValue(column="Last"))

            # Use QueueService for validation
            validation = self._queue_service.validate_equidistant_slices(
                num_slices=int(numSlices),
                first_slice=first_slice,
                last_slice=last_slice,
            )

            if not validation.is_valid:
                dialogs.show_error(self.root, "Value Error", validation.errors[0])
            else:
                self._set(self.getFocus(), "NumSlices", numSlices)
                self.context.safe_status_update(
                    "Equidistant slices set for selection.", level="info"
                )

        else:
            for item in self._row_ids:
                self._set(item, "NumSlices", numSlices)
            self.context.safe_status_update("Equidistant slices set for all entries.", level="info")

    def addToMultipleColsnRows(self, colNames: list, values: list):
        """
        Add values to multiple columns to all rows. Provide a list of column names
        and in the same order a list of values to add.

        Parameters
        ----------
        colNames : list
            List of column names.
        value : list
            List of values in order.

        """
        for item in self._row_ids:
            for idx, name in enumerate(colNames):
                self._set(item, str(name), values[idx])

    def setImgSliceDirectionAndUpdateLastSliceInTreeview(self, expDir: str):
        """
        Updates the image slice direction and corresponding 'Last' slice value
        based on user selection.

        Parameters
        ----------
        expDir : str
            The image slice direction ('XZ', 'YZ', 'XY').

        Returns
        -------
        None
        """
        path = self.getValue("Path")
        if not path:
            # Early exit if there's no path selected to avoid errors
            dialogs.show_warning(
                self.root,
                "Missing Selection",
                "Please select a valid entry in the queue table before changing the "
                "slice direction.",
            )
            return

        self.setValue("Img. Slice Dir.", expDir)

        # Use QueueService to get dimension key
        dim_key = self._queue_service.get_dimension_key_for_direction(expDir)
        if dim_key:
            self.newLastSliceToExport = octF.getXMLvalue(path, dim_key)
            self.setValue("Last", self.newLastSliceToExport)
            self.setValue("NumSlices", self.newLastSliceToExport)
        self.context.safe_status_update("Slice direction updated.", level="info")

    def updateImgSliceDirectionForAllEntries(self, expDir: str):
        """
        Updates the image slice direction and corresponding 'Last' value for
        all entries in the treeView based on the selected direction.

        Parameters
        ----------
        expDir : str
            The image slice direction ('XZ', 'YZ', 'XY').

        Returns
        -------
        None
        """
        # Use QueueService to get dimension key
        dim_key = self._queue_service.get_dimension_key_for_direction(expDir)
        if not dim_key:
            dialogs.show_warning(
                self.root, "Invalid Direction", f"'{expDir}' is not a recognized slice direction."
            )
            return

        items_updated = 0

        for item in list(self._row_ids):
            path = self._get(item, "Path")
            if not path:
                continue  # skip entries with missing path

            last_slice = octF.getXMLvalue(path, dim_key)
            self._set(item, "Img. Slice Dir.", expDir)
            self._set(item, "Last", last_slice)
            self._set(item, "NumSlices", last_slice)
            items_updated += 1

        if items_updated == 0:
            dialogs.show_warning(
                self.root,
                "No Entries Updated",
                "No entries had a valid path to apply the slice direction.",
            )
        else:
            self.context.safe_status_update(
                f"Slice direction updated for {items_updated} entries.", level="success"
            )
