"""
CarlQuant Analysis Runner (view-layer orchestration)

Thin UI/threading wrapper around the tkinter-free
``AnalysisService.analyze_specimen``. This holds everything that the pure logic
must *not* know about: the modal progress dialog, the worker thread, the
specimen-table status updates, and status-bar / error-popup messaging.

Per-slice compute, result storage and persistence are delegated to the service;
this module only translates service callbacks into UI updates.
"""
import time
import traceback
from threading import Thread

from app.view.carlquant.progress_dialog import ProgressDialog
from app.view.shared.error_handler import show_error_popup, log_error_to_file
from app.logic.carlquant import AnalysisService


def run_carl_quant(context):
    """Run CarlQuant analysis with a progress dialog and cancellation support.

    Iterates the loaded specimens on a background thread, delegating each
    specimen's analysis to :meth:`AnalysisService.analyze_specimen` while a modal
    :class:`ProgressDialog` reflects progress and offers a Cancel button.
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
            for specimen_idx, (specimen_id, specimen) in enumerate(specimen_list):
                if progress_dialog.is_cancelled():
                    cancelled = True
                    context.status_bar.update("Analysis cancelled by user", level="warning")
                    break

                progress_dialog.update_specimen(specimen_idx, specimen_id, specimen.slices)

                # Honour the user's reanalysis choice.
                choice = getattr(specimen, "analysis_choice", "new")
                if choice == "skip":
                    context.status_bar.update(
                        f"Skipped specimen {specimen_id} (user choice)", level="info"
                    )
                    specimen.status = "Skipped"
                    context.root.after(0, lambda sid=specimen_id: _set_row_status(context, sid, "Skipped"))
                    progress_dialog.complete_specimen(specimen_idx)
                    continue

                # overwrite / new: stamp metadata from the settings panel.
                specimen.measurement = context.analysis_metadata.get("measurement", 1)
                specimen.operator = context.analysis_metadata.get("operator", "OP")

                num_sound = context.region_config.get("sound", 3)
                num_lesion = context.region_config.get("lesion", 3)
                detection_method = getattr(context, "detection_method", "combined_mean")

                def on_mode(mode, workers):
                    if mode == "parallel":
                        progress_dialog.set_processing_mode("parallel", workers)
                    else:
                        progress_dialog.set_processing_mode("sequential")

                try:
                    result = AnalysisService.analyze_specimen(
                        specimen,
                        num_sound=num_sound,
                        num_lesion=num_lesion,
                        detection_method=detection_method,
                        result_lock=getattr(context, "result_lock", None),
                        save=True,
                        on_status=lambda msg: progress_dialog.update_status(msg, color="blue"),
                        on_slice_done=lambda done, total: progress_dialog.update_slice(done, total),
                        on_mode=on_mode,
                        on_error=lambda msg: context.status_bar.update(msg, level="error"),
                        is_cancelled=progress_dialog.is_cancelled,
                    )
                except Exception as exc:
                    context.status_bar.update(
                        f"Error processing {specimen_id}: {exc}", level="error"
                    )
                    progress_dialog.complete_specimen(specimen_idx)
                    continue

                # Reflect the computed status in the specimen table (main thread).
                was_cancelled = progress_dialog.is_cancelled()
                context.root.after(
                    0,
                    lambda sid=specimen_id, status=result.status, wc=was_cancelled:
                        _set_row_status(context, sid, status, lock_on_complete=not wc),
                )

                progress_dialog.complete_specimen(specimen_idx)

                if progress_dialog.is_cancelled():
                    cancelled = True
                    break

            if cancelled:
                context.status_bar.update("Analysis cancelled by user", level="warning")
            else:
                context.status_bar.update("CarlQuant analysis complete.", level="success")

        except Exception as exc:
            tb = traceback.format_exc()
            error_message = (
                f"CarlQuant Analysis Error:\n\n"
                f"Exception: {str(exc)}\n\n"
                f"Traceback:\n{tb}"
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
