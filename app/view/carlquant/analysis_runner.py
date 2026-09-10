"""
CarlQuant Analysis Runner.

Background-thread orchestrator that runs the CarlQuant analysis pipeline across
all loaded specimens. Displays a modal ProgressDialog and supports cancellation.
Delegates per-specimen computation to AnalysisService.analyze_specimen.

Key contents:
- run_carl_quant: Entry point that spawns the analysis worker thread.
- worker: Iterates specimens, updates progress, and handles cancellation.
- ProgressDialog integration: Thread-safe UI updates for specimen and slice progress.

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

import time
import traceback
from threading import Thread

from app.logic.carlquant.parallel_analysis import ParallelSpecimenCoordinator
from app.view.carlquant.progress_dialog import ProgressDialog
from app.view.shared.error_handler import log_error_to_file, show_error_popup


def run_carl_quant(context):
    """Run CarlQuant analysis with a progress dialog and cancellation support.

    Dispatches the loaded specimens to a single process pool via
    :class:`ParallelSpecimenCoordinator` from a background thread -- one task per
    specimen -- while a modal :class:`ProgressDialog` reflects progress and offers
    a Cancel button. Progress is reported per specimen; each worker analyses all
    of its specimen's slices and saves the results itself.
    """

    def worker():
        specimen_list = list(context.specimen_data.items())

        # Honour the user's reanalysis choice before sizing the dialog, so the
        # overall progress bar counts only the specimens that will actually run.
        pending = []
        for specimen_id, specimen in specimen_list:
            if getattr(specimen, "analysis_choice", "new") == "skip":
                context.status_bar.update(
                    f"Skipped specimen {specimen_id} (user choice)", level="info"
                )
                specimen.status = "Skipped"
                context.root.after(
                    0, lambda sid=specimen_id: _set_row_status(context, sid, "Skipped")
                )
                continue
            # overwrite / new: stamp metadata from the settings panel. This must
            # happen before submission -- workers get a copy of the specimen and
            # cannot reach back into the application context.
            specimen.measurement = context.analysis_metadata.get("measurement", 1)
            specimen.operator = context.analysis_metadata.get("operator", "OP")
            pending.append((specimen_id, specimen))

        # Create the progress dialog on the main thread.
        progress_dialog = None

        def create_dialog():
            nonlocal progress_dialog
            progress_dialog = ProgressDialog(
                context.root,
                total_specimens=max(len(pending), 1),
                specimen_names=[sid for sid, _ in pending],
            )

        context.root.after(0, create_dialog)
        while progress_dialog is None:
            time.sleep(0.01)

        cancelled = False

        try:
            num_sound = context.region_config.get("sound", 3)
            num_lesion = context.region_config.get("lesion", 3)
            detection_method = getattr(context, "detection_method", "combined_mean")

            by_id = {sid: specimen for sid, specimen in pending}
            total_specimens = len(pending)
            total_slices = sum(specimen.slices for _, specimen in pending)
            coordinator = ParallelSpecimenCoordinator()

            state = {"done": 0, "slices": 0}

            def on_mode(mode, workers):
                progress_dialog.set_processing_mode(mode, workers if mode == "parallel" else None)
                progress_dialog.update_specimen(
                    0, f"{total_specimens} specimens ({workers} workers)", max(total_slices, 1)
                )

            def on_specimen_done(result):
                """Called on the coordinator thread as each specimen finishes."""
                state["done"] += 1
                state["slices"] += result.processed_count
                done = state["done"]

                # The worker mutated its own copy, so apply the status here.
                specimen = by_id.get(result.specimen_id)
                if specimen is not None:
                    specimen.status = result.status

                if result.status.startswith("Error"):
                    context.status_bar.update(
                        f"Error processing {result.specimen_id}: {result.status}", level="error"
                    )

                was_cancelled = progress_dialog.is_cancelled()
                context.root.after(
                    0,
                    lambda sid=result.specimen_id, status=result.status, wc=was_cancelled: (
                        _set_row_status(context, sid, status, lock_on_complete=not wc)
                    ),
                )

                if state["slices"]:
                    progress_dialog.update_slice(state["slices"] - 1, max(total_slices, 1))
                progress_dialog.complete_specimen(done - 1)
                progress_dialog.update_status(
                    f"Completed {result.specimen_id} ({done}/{total_specimens})", color="blue"
                )

                # Cancellation is observed at specimen granularity: stop feeding
                # the pool, let in-flight specimens finish.
                if was_cancelled:
                    coordinator.cancel()

            if progress_dialog.is_cancelled():
                cancelled = True
            elif pending:
                coordinator.run(
                    [specimen for _, specimen in pending],
                    num_sound=num_sound,
                    num_lesion=num_lesion,
                    detection_method=detection_method,
                    on_mode=on_mode,
                    progress_callback=on_specimen_done,
                )
                cancelled = progress_dialog.is_cancelled()

            if cancelled:
                context.status_bar.update("Analysis cancelled by user", level="warning")
            else:
                context.status_bar.update("CarlQuant analysis complete.", level="success")

        except Exception as exc:
            tb = traceback.format_exc()
            error_message = (
                f"CarlQuant Analysis Error:\n\nException: {str(exc)}\n\nTraceback:\n{tb}"
            )
            log_error_to_file("run_carl_quant.worker", (), {}, "Worker thread exception", tb)
            context.root.after(
                0, lambda: show_error_popup("CarlQuant Analysis Error", error_message)
            )
            context.status_bar.update(f"Analysis failed: {str(exc)}", level="error")
            cancelled = True

        finally:
            if progress_dialog:
                progress_dialog.finish(cancelled=cancelled)

    Thread(target=worker, daemon=True).start()


def _set_row_status(context, specimen_id, status, *, lock_on_complete=False):
    """Update a specimen's status cell in the specimen table (main-thread only)."""
    specimen_panel = context.get_panel("carl_specimen")
    if specimen_panel:
        for row_idx in range(specimen_panel.sheet.total_rows()):
            if specimen_panel.sheet.get_cell_data(row_idx, 0) == specimen_id:
                specimen_panel.sheet.set_cell_data(row_idx, 2, status)
                specimen_panel._set_column_widths()
                if status == "Completed":
                    specimen_panel.highlight_completed_row(row_idx)
                break

    # Lock the region dropdown once a specimen completes (unless cancelled).
    if lock_on_complete and status == "Completed":
        settings_panel = context.get_panel("carl_settings")
        if settings_panel:
            settings_panel.lock_region_dropdown(True)
