# -*- coding: utf-8 -*-
"""
Created on Mon Sep 22 09:45:35 2025

@author: Tobias Meissner
"""

import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as ttk
from datetime import datetime
import csv
import textwrap



class StatusBar:
    def __init__(self, parent, *, bootstyle="secondary"):
        self.parent = parent
        self.root = parent.winfo_toplevel()
        self.default_bootstyle = bootstyle

        self.frame = ttk.Frame(parent, bootstyle=bootstyle)

        self.label = ttk.Label(self.frame, text="Ready", anchor="w", bootstyle=bootstyle, foreground="#E8E8E8")
        self.label.pack(fill="x", padx=5, pady=2)
        self.label.bind("<Button-1>", self.show_log_window)

        self._queue = []
        self._clear_after_id = None
        self._log = []

    def attach_context(self, context):
        if context is None:
            return
        context.status_bar = self
        register_frame = getattr(context, "register_frame", None)
        if callable(register_frame):
            register_frame("status", self.frame)

    def update(self, message: str, level: str = "info", duration: int = 2000):
        self.frame.after(0, lambda: self._enqueue_message(message, level, duration))

    def _enqueue_message(self, message: str, level: str, duration: int):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self._queue.append((full_message, level, duration))
        self._log.append((full_message, level))
        if len(self._queue) == 1:
            self._display_next()


    def _display_next(self):
        if not self._queue:
            self.clear()
            return

        message, level, duration = self._queue[0]

        # Truncate if too long
        max_chars = 200  # Adjust based on your layout
        display_msg = message if len(message) <= max_chars else message[:max_chars - 3] + "..."

        self.label.config(text=display_msg)
        self.label.tooltip_text = message  # Store full message for tooltip

        # Optional: add tooltip
        self._add_tooltip(self.label, message)

        colors = {
            "info": "#E8E8E8",      # Bright gray for info
            "success": "#4CAF50",   # Bright green for success
            "warning": "#FFA726",   # Bright orange for warning
            "error": "#EF5350",     # Bright red for error
        }
        fg = colors.get(level, "#E8E8E8")
        self.label.config(foreground=fg)

        if self._clear_after_id:
            self.label.after_cancel(self._clear_after_id)
        self._clear_after_id = self.label.after(duration, self._advance_queue)

    def _add_tooltip(self, widget, text, wrap_length=100):
        wrapped_text = textwrap.fill(text, width=wrap_length)

        tooltip = tk.Toplevel(widget)
        tooltip.withdraw()
        tooltip.overrideredirect(True)
        tooltip.attributes("-topmost", True)

        label = tk.Label(tooltip, text=wrapped_text, background="lightyellow",
                         relief="solid", borderwidth=1, justify="left", anchor="w")
        label.pack(ipadx=5, ipady=3)

        def show_tooltip(event):
            x = event.x_root + 10
            y = event.y_root + 10
            tooltip.geometry(f"+{x}+{y}")
            tooltip.deiconify()

        def hide_tooltip(event):
            tooltip.withdraw()

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)



    def _advance_queue(self):
        self._queue.pop(0)
        self._clear_after_id = None
        self._display_next()

    def clear(self):
        self.label.config(text="Ready", bootstyle=self.default_bootstyle)
        self.label.config(foreground="#E8E8E8")

    def show_log_window(self, event=None):
        log_window = tk.Toplevel(self.root)
        log_window.title("Message Log")
        log_window.geometry("700x500")

        # Filter dropdown
        filter_var = tk.StringVar(value="All")
        filter_menu = ttk.Combobox(log_window, textvariable=filter_var, values=["All",
                                                                                "info",
                                                                                "success",
                                                                                "warning",
                                                                                "error"],
                                   state="readonly")
        filter_menu.pack(pady=5)

        # Log display
        log_frame = ttk.Frame(log_window)
        log_frame.pack(expand=True, fill="both", padx=10, pady=5)

        log_text = tk.Text(log_frame, wrap="word", state="normal")
        log_text.pack(expand=True, fill="both")

        def refresh_log():
            log_text.config(state="normal")
            log_text.delete("1.0", "end")
            for msg, level in self._log:
                if filter_var.get() == "All" or level == filter_var.get():
                    tag = f"{level}_tag"
                    log_text.insert("end", f"{msg}\n", tag)
            log_text.config(state="disabled")

        # Color tags
        log_text.tag_config("info_tag", background="#d3d3d3", foreground="black")
        log_text.tag_config("success_tag", background="#c6f6d5", foreground="black")
        log_text.tag_config("warning_tag", background="#fff3cd", foreground="black")
        log_text.tag_config("error_tag", background="#f8d7da", foreground="black")

        filter_menu.bind("<<ComboboxSelected>>", lambda e: refresh_log())
        refresh_log()

        # RexView buttons
        export_frame = ttk.Frame(log_window)
        export_frame.pack(pady=5)

        def export_txt():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt")],
                title="Save log as TXT"
            )
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    for msg, level in self._log:
                        f.write(f"{level.upper}: {msg}\n")


        def export_csv():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                title="Save log as CSV"
            )
            if file_path:
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Level", "Message"])
                    for msg, level in self._log:
                        writer.writerow([level, msg])


        ttk.Button(export_frame, text="RexView as TXT", command=export_txt, bootstyle="info").pack(side="left", padx=5)
        ttk.Button(export_frame, text="RexView as CSV", command=export_csv, bootstyle="info").pack(side="left", padx=5)



