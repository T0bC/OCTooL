"""
RexView Export Worker

Top-level, picklable worker for process-based parallel export.

This module deliberately contains only module-level functions (no closures,
no tkinter, no bound state) so it can be dispatched to a
``concurrent.futures.ProcessPoolExecutor`` on platforms that use the ``spawn``
start method (e.g. Windows). Each worker builds its own ``ExportService``,
exports a single OCT file, and returns a small, picklable ``ExportResult``.
"""
from __future__ import annotations

import traceback

from app.logic.rexview.export_service import ExportService
from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportResult


def export_one_file(
    file_path: str,
    params: SliceExportParams,
    config: ExportConfig,
) -> ExportResult:
    """
    Export a single OCT file in isolation and return a picklable result.

    This is the unit of work submitted to a process pool. It must not raise:
    any failure is captured into the returned ``ExportResult.error`` so the
    coordinator can keep processing the remaining files.

    Args:
        file_path: Path to the OCT file to export.
        params: Per-file slice export parameters.
        config: Export configuration.

    Returns:
        ExportResult with exported file paths (as strings), a failed-slice
        count, and an optional error message.
    """
    service = ExportService()
    try:
        exported = service.run_export(file_path, params, config)
        exported_files = [str(p) for p in exported]
        failed_count = max(params.num_slices - len(exported_files), 0)
        return ExportResult(
            file_path=file_path,
            exported_files=exported_files,
            failed_count=failed_count,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 - must never crash the worker
        return ExportResult(
            file_path=file_path,
            exported_files=[],
            failed_count=params.num_slices,
            error=f"{exc}\n{traceback.format_exc()}",
        )
