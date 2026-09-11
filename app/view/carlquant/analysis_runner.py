"""
CarlQuant Analysis Runner.

Background-thread orchestrator that runs the CarlQuant analysis pipeline across
all loaded specimens. Displays a modal ProgressDialog and supports cancellation.
Delegates computation to BatchSliceCoordinator, which drives a single process
pool over a flat queue holding every slice of every specimen, so that pool
startup is paid once per batch instead of once per specimen and the parent saves
one specimen while the workers already compute the next.

Key contents:
- run_carl_quant: Entry point that spawns the analysis worker thread.
- worker: Prepares specimens, runs the batch coordinator, handles cancellation.
- ProgressDialog integration: Thread-safe UI updates for batch slice progress.

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

from app.logic.carlquant.parallel_analysis import BatchSliceCoordinator
from app.view.carlquant.progress_dialog import ProgressDialog
from app.view.shared.error_handler import log_error_to_file, show_error_popup


def run_carl_quant(context):
    """Run CarlQuant analysis with a progress dialog and cancellation support.

    Stamps the settings-panel metadata onto every specimen the user wants
    analysed, then hands the whole batch to :class:`BatchSliceCoordinator` on a
    background thread while a modal :class:`ProgressDialog` reflects batch-wide
    slice progress and offers a Cancel button.
    """

    def worker():
        specimen_list = list(context.specimen_data.items())
        specimen_ids = [sid for sid, _ in specimen_list]

        # Create the progress dialog on the main thread.
        progress_dialog = None

        def create_dialog():
            nonlocal progress_dialog
            progress_dialog = ProgressDialog(
                context.root,
                total_specimens=len(specimen_list),
                specimen_names=specimen_ids,
            )

        context.root.after(0, create_dialog)
        while progress_dialog is None:
            time.sleep(0.01)

        cancelled = False

        try:
            num_sound = context.region_config.get("sound", 3)
            num_lesion = context.region_config.get("lesion", 3)
            detection_method = getattr(context, "detection_method", "combined_mean")
            measurement = context.analysis_metadata.get("measurement", 1)
            operator = context.analysis_metadata.get("operator", "OP")

            # Split the batch by the user's reanalysis choice before any compute.
            queued = []
            for specimen_id, specimen in specimen_list:
                if getattr(specimen, "analysis_choice", "new") == "skip":
                    context.status_bar.update(
                        f"Skipped specimen {specimen_id} (user choice)", level="info"
                    )
                    specimen.status = "Skipped"
                    context.root.after(
                        0, lambda sid=specimen_id: _set_row_status(context, sid, "Skipped")
                    )
                    progress_dialog.complete_specimen(specimen_id)
                    continue

                # overwrite / new: stamp metadata from the settings panel.
                specimen.measurement = measurement
                specimen.operator = operator
                queued.append(specimen)

            def on_mode(mode, workers):
                if mode == "parallel":
                    progress_dialog.set_processing_mode("parallel", workers)
                else:
                    progress_dialog.set_processing_mode("sequential")

            def on_specimen_done(result):
                # Specimens finish out of order, so the row is updated by id.
                was_cancelled = progress_dialog.is_cancelled()
                context.root.after(
                    0,
                    lambda sid=result.specimen_id, status=result.status, wc=was_cancelled: (
                        _set_row_status(context, sid, status, lock_on_complete=not wc)
                    ),
                )
                progress_dialog.complete_specimen(result.specimen_id)

            progress_dialog.start_batch(sum(s.slices for s in queued))

            BatchSliceCoordinator().run(
                queued,
                num_sound=num_sound,
                num_lesion=num_lesion,
                detection_method=detection_method,
                save=True,
                result_lock=getattr(context, "result_lock", None),
                on_mode=on_mode,
                on_status=lambda msg: progress_dialog.update_status(msg, color="blue"),
                on_slice_done=progress_dialog.update_batch_slice,
                on_specimen_done=on_specimen_done,
                on_error=lambda msg: context.status_bar.update(msg, level="error"),
                is_cancelled=progress_dialog.is_cancelled,
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
