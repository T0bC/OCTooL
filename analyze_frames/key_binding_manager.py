# -*- coding: utf-8 -*-
"""
Created on Fri Sep 12 09:18:04 2025

@author: meissnerto
"""

from utils.error_handler import handle_errors
from datetime import datetime
from analyze_frames.undo_panel import UndoPanel
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class KeybindingManager:
    @handle_errors("KeybindingManager.__init__")
    def __init__(self, canvas, sheet, column_map, annotate_panel):
        self.canvas = canvas
        self.sheet = sheet
        self.column_map = column_map
        self.annotate_panel = annotate_panel
        self.handlers = {
            "Continuous": self.handle_continuous,
            "Percentage": self.handle_percentage,
            "Boolean": self.handle_boolean,
            "Categorical": self.handle_categorical,
            "Ordinal": self.handle_ordinal,
            "Integer": self.handle_integer,
            "Float": self.handle_float,
            "Text/String": self.handle_text_string
        }
        self.save_timer = None

        self.undo_stack = []
        self.annotate_panel.window.bind("<Control-z>", lambda e: self.undo_last())
        self.annotate_panel.window.bind("<Control-u>", lambda e: self.open_undo_panel())

    # %% Keybindings
    @handle_errors("KeybindingManager.register_keybindings")
    def register_keybindings(self):
        for key, col_info in self.column_map.items():
            col_name = col_info["col_name"]
            data_type = col_info["data_type"]
            self.annotate_panel.window.bind(f"<{key.lower()}>", lambda e, k=key: self.dispatch_with_length(k))

    # %% Run the different Data Handlers
    def dispatch_with_length(self, key):
        slice_index = int(self.annotate_panel.scale.get()) - 1
        col_info = self.column_map[key]
        col_name = col_info["col_name"]
        data_type = col_info["data_type"]
        color = col_info.get("color", "#FFFFFF")

        # Only commit annotation if data type is Continuous
        if data_type == "Continuous":
            annotation_id = self.annotate_panel.commit_annotation(col_name, color=color)
            length = self.annotate_panel.get_annotation_length(slice_index)
            self.dispatch(key, value=round(length, 2), annotation_id=annotation_id)
        else:
            # For other types, just dispatch without committing annotation
            self.dispatch(key, annotation_id=None)

        self.debounce_save()

    @handle_errors("KeybindingManager.dispatch")
    def dispatch(self, key, value=None, annotation_id=None):
        col_info = self.column_map[key]
        col_name = col_info["col_name"]
        data_type = col_info["data_type"]
        color = col_info.get("color", "#FFFFFF")  # fallback
        col_index = self.sheet.headers().index(col_name)
        slice_index = int(self.annotate_panel.scale.get()) - 1  # zero-based

        total_rows = self.sheet.total_rows()
        if slice_index >= total_rows:
            for _ in range(slice_index - total_rows + 1):
                self.sheet.insert_row(idx=total_rows)

        self.update_metadata(slice_index)

        handler = self.handlers.get(data_type)
        if handler:
                handler(slice_index, col_index, color, data_type, value, annotation_id)
        else:
            print(f"No handler found for data type: {data_type}")

     # %% Save Measurements, Annotations and Config
    def save_measurements_threaded(self):
        from concurrent.futures import ThreadPoolExecutor

        results_panel = self.annotate_panel.context.get_panel("results")
        if results_panel:
            executor = ThreadPoolExecutor(max_workers=1)
            executor.submit(results_panel.save_measurements)


    def _save_all(self):
        config_manager = self.annotate_panel.context.config_manager
        metadata_panel = self.annotate_panel.context.get_panel("metadata")
        results_panel = self.annotate_panel.context.get_panel("results")
        add_columns_panel = self.annotate_panel.context.get_panel("add_columns")

        image_folder = self.annotate_panel.context.image_folder
        if image_folder:
            config_manager.save_config_to_folder(image_folder, metadata_panel, results_panel, add_columns_panel)
            self.annotate_panel.save_current_annotations()
            self.save_measurements_threaded()


    def debounce_save(self, delay=1.5):
        if self.save_timer:
            self.save_timer.cancel()

        self.save_timer = threading.Timer(delay, self._save_all)
        self.save_timer.start()


    @handle_errors("KeybindingManager.update_metadata")
    def update_metadata(self, row_index):
        sheet = self.sheet
        headers = sheet.headers()
        context = self.annotate_panel.context

        # Panels
        metadata_panel = context.get_panel("metadata")
        image_folder = context.image_folder

        # Values
        specimen_name = image_folder.name if image_folder else "Unknown"
        operator = metadata_panel.operatorEntry.get() if metadata_panel else ""
        measurement = metadata_panel.measurementEntry.get() if metadata_panel else ""
        system = metadata_panel.systemEntry.get() if metadata_panel else ""
        date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Column updates
        values = {
            "SPECIMEN_NAME": specimen_name,
            "SLICE": str(row_index + 1),
            "OPERATOR": operator,
            "MEASUREMENT": measurement,
            "SYSTEM": system,
            "DATE_TIME": date_time
        }

        for col_name, val in values.items():
            if col_name in headers:
                col_index = headers.index(col_name)
                sheet.set_cell_data(row_index, col_index, val)


    # %% Data Type Handlers
    @handle_errors("KeybindingManager.handle_continuous")
    def handle_continuous(self, row, col, color, data_type, value=None, annotation_id=None):
        # Get current value from sheet
        current_value = self.sheet.get_cell_data(row, col)

        # Parse current value as float (default to 0.0 if empty or invalid)
        try:
            current_float = float(current_value)
        except (ValueError, TypeError):
            current_float = 0.0

        # Parse new measured value
        if value is None:
            print("No measurement value provided.")
            return

        try:
            measured_value = float(value)
        except (ValueError, TypeError):
            print(f"Invalid measurement value: {value}")
            return

        # Add new measurement to existing value
        new_value = current_float + measured_value

        # Record undo info
        self.undo_stack.append({
            "row": row,
            "col": col,
            "col_name": self.sheet.headers()[col],
            "old_value": current_value,
            "new_value": new_value,
            "key": data_type,
            "feature": annotation_id.split("_")[0] if annotation_id else None,
            "annotation_id": annotation_id,
            "timestamp": datetime.now(),
            "color": color
        })

        # Update the sheet
        self.sheet.set_cell_data(row, col, f"{new_value:.2f}")
        self.sheet.deselect("all")
        self.flash_cell(row, col)


    @handle_errors("KeybindingManager.handle_boolean")
    def handle_boolean(self, row, col, color, data_type, value=None, annotation_id=None):
        current_value = self.sheet.get_cell_data(row, col)

        # Toggle logic: if current is NO-like, switch to YES; otherwise switch to NO
        new_value = "YES" if str(current_value).strip().upper() in ["NO", "0", "FALSE", ""] else "NO"

        # Record undo info
        self.undo_stack.append({
            "row": row,
            "col": col,
            "col_name": self.sheet.headers()[col],
            "old_value": current_value,
            "new_value": new_value,
            "key": data_type,
            "feature": annotation_id.split("_")[0] if annotation_id else None,
            "annotation_id": annotation_id,
            "timestamp": datetime.now(),
            "color": color
        })

        # Update sheet
        self.sheet.set_cell_data(row, col, new_value)
        self.sheet.deselect("all")
        self.flash_cell(row, col)


    @handle_errors("KeybindingManager.handle_percentage")
    def handle_percentage(self, row, col, color, data_type, value=None, annotation_id=None):
        current_value = self.sheet.get_cell_data(row, col)

        try:
            current_percent = int(current_value.replace("%", "").strip())
        except (ValueError, TypeError):
            current_percent = 0

        new_percent = min(current_percent + 5, 100)

        self.undo_stack.append({
            "row": row,
            "col": col,
            "col_name": self.sheet.headers()[col],
            "old_value": current_value,
            "new_value": f"{new_percent}%",
            "key": data_type,
            "feature": annotation_id.split("_")[0] if annotation_id else None,
            "annotation_id": annotation_id,
            "timestamp": datetime.now(),
            "color": color
        })

        self.sheet.set_cell_data(row, col, f"{new_percent}%")
        self.sheet.deselect("all")
        self.flash_cell(row, col)


    @handle_errors("KeybindingManager.handle_categorical")
    def handle_categorical(self, row, col, color, data_type, value=None, annotation_id=None):
        current_value = self.sheet.get_cell_data(row, col)

        # Try to parse current value as integer
        try:
            current_int = int(current_value)
        except (ValueError, TypeError):
            current_int = -1  # Start from -1 so first press sets to 0

        # Increment category index
        new_value = current_int + 1

        # Record undo info
        self.undo_stack.append({
            "row": row,
            "col": col,
            "col_name": self.sheet.headers()[col],
            "old_value": current_value,
            "new_value": new_value,
            "key": data_type,
            "feature": annotation_id.split("_")[0] if annotation_id else None,
            "annotation_id": annotation_id,
            "timestamp": datetime.now(),
            "color": color
        })

        # Update sheet
        self.sheet.set_cell_data(row, col, str(new_value))
        self.sheet.deselect("all")
        self.flash_cell(row, col)


    @handle_errors("KeybindingManager.handle_ordinal")
    def handle_ordinal(self, row, col, color, data_type, value=None, annotation_id=None):
        current_value = self.sheet.get_cell_data(row, col)

        # Try to parse current value as integer
        try:
            current_int = int(current_value)
        except (ValueError, TypeError):
            current_int = 0

        # Increment score
        new_value = current_int + 1

        # Record undo info
        self.undo_stack.append({
            "row": row,
            "col": col,
            "col_name": self.sheet.headers()[col],
            "old_value": current_value,
            "new_value": new_value,
            "key": data_type,
            "feature": annotation_id.split("_")[0] if annotation_id else None,
            "annotation_id": annotation_id,
            "timestamp": datetime.now(),
            "color": color
        })

        # Update sheet
        self.sheet.set_cell_data(row, col, str(new_value))
        self.sheet.deselect("all")
        self.flash_cell(row, col)


    @handle_errors("KeybindingManager.handle_integer")
    def handle_integer(self, row, col, color, data_type, value=None, annotation_id=None):
        self.prompt_for_value(row, col, color, data_type, value, annotation_id)

    @handle_errors("KeybindingManager.handle_float")
    def handle_float(self, row, col, color, data_type, value=None, annotation_id=None):
        self.prompt_for_value(row, col, color, data_type, value, annotation_id)

    @handle_errors("KeybindingManager.handle_text_string")
    def handle_text_string(self, row, col, color, data_type, value=None, annotation_id=None):
        self.prompt_for_value(row, col, color, data_type, value, annotation_id)





    # %% Visual Feedback in tksheet results table
    def flash_cell(self, row, col, bg="#FFD700", fg="#000000", duration=800):
        # Highlight the cell
        self.sheet.highlight_cells(
            row=row,
            column=col,
            bg=bg,
            fg=fg,
            overwrite=True
        )

        # Schedule dehighlight after `duration` milliseconds
        self.sheet.after(duration, lambda: self.sheet.dehighlight_cells(
            row=row,
            column=col
        ))

    # %% Undo Panel
    def open_undo_panel(self):
        UndoPanel(self.annotate_panel.context, self.undo_stack)


    def undo_last(self):
        if not self.undo_stack:
            print("Undo stack is empty.")
            return

        last_action = self.undo_stack.pop()
        row = last_action["row"]
        col = last_action["col"]
        old_value = last_action["old_value"]
        annotation_id = last_action.get("annotation_id")

        self.sheet.set_cell_data(row, col, old_value)
        self.flash_cell(row, col, bg="#FF6347")

        # Remove annotation if applicable
        if annotation_id:
            annotations = self.annotate_panel.slice_annotations.get(row, [])
            self.annotate_panel.slice_annotations[row] = [
                a for a in annotations if a.get("id") != annotation_id
            ]
            self.annotate_panel.draw_annotation()
            self.annotate_panel.save_current_annotations()
            self.annotate_panel.draw_overlay_annotations(row)


    def prompt_for_value(self, row, col, color, data_type, value=None, annotation_id=None):
        col_name = self.sheet.headers()[col]

        def on_submit():
            raw_input = entry.get().strip()
            self.popup.destroy()

            # Normalize decimal comma for float
            if data_type == "Float":
                raw_input = raw_input.replace(",", ".")

            try:
                if data_type == "Integer":
                    if "." in raw_input:
                        messagebox.showwarning("Invalid Input", "Please enter a whole number for Integer data.")
                        return
                    parsed_value = int(raw_input)

                elif data_type == "Float":
                    parsed_value = float(raw_input)

                elif data_type == "Text/String":
                    parsed_value = raw_input

                else:
                    print(f"Unsupported data type: {data_type}")
                    return

                # Get current value for undo tracking
                current_value = self.sheet.get_cell_data(row, col)

                # Record undo info
                self.undo_stack.append({
                    "row": row,
                    "col": col,
                    "col_name": col_name,
                    "old_value": current_value,
                    "new_value": parsed_value,
                    "key": data_type,
                    "feature": annotation_id.split("_")[0] if annotation_id else None,
                    "annotation_id": annotation_id,
                    "timestamp": datetime.now(),
                    "color": color
                })

                # Update the sheet
                self.sheet.set_cell_data(row, col, str(parsed_value))
                self.sheet.deselect("all")
                self.flash_cell(row, col)

            except ValueError:
                messagebox.showerror("Invalid Input", f"Could not parse value: {raw_input}")

        # Create popup
        self.popup = tk.Toplevel(self.annotate_panel.window)
        self.popup.title(f"Enter {data_type} Value")
        self.popup.geometry("250x100")
        self.popup.transient(self.annotate_panel.window)
        self.popup.grab_set()

        label = ttk.Label(self.popup, text=f"Enter {data_type} value:")
        label.pack(pady=5)

        entry = ttk.Entry(self.popup)
        entry.pack(pady=5)
        entry.focus()

        entry.bind("<Return>", lambda event: on_submit())


        submit_btn = ttk.Button(self.popup, text="Submit", command=on_submit)
        submit_btn.pack(pady=5)



