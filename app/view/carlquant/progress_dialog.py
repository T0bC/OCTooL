# -*- coding: utf-8 -*-
"""
Progress dialog for CarlQuant analysis with cancellation support.

Created on Thu Oct 09 2025
"""

import tkinter as tk
from tkinter import ttk
import threading


class ProgressDialog:
    """
    A modal progress dialog for CarlQuant analysis.
    
    Features:
    - Shows current specimen being processed
    - Shows slice progress within specimen
    - Overall progress across all specimens
    - Cancel button with graceful interruption
    - Thread-safe updates from worker threads
    """
    
    def __init__(self, parent, total_specimens, specimen_names):
        """
        Initialize the progress dialog.
        
        Args:
            parent: Parent window (root)
            total_specimens: Total number of specimens to process
            specimen_names: List of specimen IDs/names
        """
        self.parent = parent
        self.total_specimens = total_specimens
        self.specimen_names = specimen_names
        self.cancel_requested = False
        self._lock = threading.Lock()
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("CarlQuant Analysis Progress")
        self.dialog.geometry("500x280")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self._center_dialog()
        
        # Prevent closing via X button (use Cancel instead)
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Build UI
        self._build_ui()
        
    def _center_dialog(self):
        """Center the dialog on the parent window."""
        self.dialog.update_idletasks()
        
        # Get parent position and size
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Get dialog size
        dialog_width = self.dialog.winfo_width()
        dialog_height = self.dialog.winfo_height()
        
        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.dialog.geometry(f"+{x}+{y}")
    
    def _build_ui(self):
        """Build the dialog UI components."""
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(
            main_frame,
            text="Processing CarlQuant Analysis",
            font=("TkDefaultFont", 12, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Overall progress section
        overall_frame = ttk.LabelFrame(main_frame, text="Overall Progress", padding=10)
        overall_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.overall_label = ttk.Label(
            overall_frame,
            text=f"Specimen 0 of {self.total_specimens}"
        )
        self.overall_label.pack(anchor=tk.W)
        
        self.overall_progress = ttk.Progressbar(
            overall_frame,
            mode='determinate',
            maximum=self.total_specimens
        )
        self.overall_progress.pack(fill=tk.X, pady=(5, 0))
        
        # Processing mode section
        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(mode_frame, text="Processing Mode:", font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT)
        self.mode_label = ttk.Label(
            mode_frame,
            text="Initializing...",
            foreground="blue"
        )
        self.mode_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Current specimen section
        specimen_frame = ttk.LabelFrame(main_frame, text="Current Specimen", padding=10)
        specimen_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.specimen_label = ttk.Label(
            specimen_frame,
            text="Waiting to start..."
        )
        self.specimen_label.pack(anchor=tk.W)
        
        self.slice_label = ttk.Label(
            specimen_frame,
            text="Slice 0 of 0"
        )
        self.slice_label.pack(anchor=tk.W, pady=(5, 0))
        
        self.slice_progress = ttk.Progressbar(
            specimen_frame,
            mode='determinate',
            maximum=100
        )
        self.slice_progress.pack(fill=tk.X, pady=(5, 0))
        
        # Status label
        self.status_label = ttk.Label(
            main_frame,
            text="",
            foreground="gray"
        )
        self.status_label.pack(pady=(5, 10))
        
        # Cancel button
        self.cancel_button = ttk.Button(
            main_frame,
            text="Cancel",
            command=self._on_cancel,
            bootstyle="danger"
        )
        self.cancel_button.pack()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        with self._lock:
            if not self.cancel_requested:
                self.cancel_requested = True
                self.cancel_button.config(state=tk.DISABLED)
                self.status_label.config(
                    text="Cancelling... waiting for current slice(s) to finish",
                    foreground="orange"
                )
    
    def is_cancelled(self):
        """Check if cancellation was requested (thread-safe)."""
        with self._lock:
            return self.cancel_requested
    
    def update_specimen(self, specimen_index, specimen_id, total_slices):
        """
        Update progress for a new specimen.
        
        Args:
            specimen_index: 0-based index of current specimen
            specimen_id: ID/name of the specimen
            total_slices: Total number of slices in this specimen
        """
        def _update():
            self.overall_progress['value'] = specimen_index
            self.overall_label.config(
                text=f"Specimen {specimen_index + 1} of {self.total_specimens}"
            )
            self.specimen_label.config(text=f"Processing: {specimen_id}")
            self.slice_progress['maximum'] = total_slices
            self.slice_progress['value'] = 0
            self.slice_label.config(text=f"Slice 0 of {total_slices}")
        
        # Schedule update on main thread
        self.dialog.after(0, _update)
    
    def update_slice(self, slice_index, total_slices):
        """
        Update progress for slice processing.
        
        Args:
            slice_index: 0-based index of current slice
            total_slices: Total number of slices
        """
        def _update():
            self.slice_progress['value'] = slice_index + 1
            self.slice_label.config(
                text=f"Slice {slice_index + 1} of {total_slices}"
            )
        
        # Schedule update on main thread
        self.dialog.after(0, _update)
    
    def update_status(self, message, color="gray"):
        """
        Update the status message.
        
        Args:
            message: Status message to display
            color: Text color (default: gray)
        """
        def _update():
            self.status_label.config(text=message, foreground=color)
        
        # Schedule update on main thread
        self.dialog.after(0, _update)
    
    def set_processing_mode(self, mode, num_workers=None):
        """
        Set the processing mode display.
        
        Args:
            mode: "parallel" or "sequential"
            num_workers: Number of workers (for parallel mode)
        """
        def _update():
            if mode == "parallel":
                text = f"Parallel ({num_workers} workers)" if num_workers else "Parallel"
                color = "green"
            else:
                text = "Sequential"
                color = "blue"
            self.mode_label.config(text=text, foreground=color)
        
        # Schedule update on main thread
        self.dialog.after(0, _update)
    
    def complete_specimen(self, specimen_index):
        """
        Mark a specimen as complete.
        
        Args:
            specimen_index: 0-based index of completed specimen
        """
        def _update():
            self.overall_progress['value'] = specimen_index + 1
            self.overall_label.config(
                text=f"Specimen {specimen_index + 1} of {self.total_specimens}"
            )
        
        # Schedule update on main thread
        self.dialog.after(0, _update)
    
    def finish(self, cancelled=False):
        """
        Close the dialog when processing is complete.
        
        Args:
            cancelled: Whether the process was cancelled
        """
        def _finish():
            if cancelled:
                self.status_label.config(
                    text="Analysis cancelled by user",
                    foreground="orange"
                )
            else:
                self.status_label.config(
                    text="Analysis complete!",
                    foreground="green"
                )
            
            # Close dialog after a short delay
            self.dialog.after(1000, self.close)
        
        # Schedule on main thread
        self.dialog.after(0, _finish)
    
    def close(self):
        """Close the dialog."""
        try:
            self.dialog.grab_release()
            self.dialog.destroy()
        except:
            pass  # Dialog may already be destroyed
    
    def show(self):
        """Show the dialog (blocks until closed)."""
        # This is called from main thread, so dialog is already visible
        # Just ensure it's on top
        self.dialog.lift()
        self.dialog.focus_force()
