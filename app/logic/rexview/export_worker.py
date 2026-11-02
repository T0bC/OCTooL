"""
RexView Export Worker.

Key contents:
- export_one_file: Top-level picklable worker that builds an ExportService and
  exports a single OCT file, capturing any failure into ExportResult.
- init_worker: ProcessPoolExecutor initializer; installs the shared progress
  queue / cancel event and limits BLAS threads for the worker process.
- report_slice: Pushes a per-slice progress message to the coordinator.

Top-level, picklable worker for process-based parallel export. Contains only
module-level functions (no closures, no tkinter, no bound state) so it can be
dispatched to a ProcessPoolExecutor on Windows (spawn). Each worker builds its
own ExportService, exports a single OCT file, and returns a small, picklable
ExportResult.

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

from __future__ import annotations

import traceback
from typing import Any

from app.logic.rexview.export_service import ExportService
from app.logic.rexview.models import ExportConfig, ExportResult, SliceExportParams

# Per-process state installed by ``init_worker``. Multiprocessing queues/events
# cannot travel through ``submit`` arguments, but they can be handed to a child
# process at start-up (``initargs``), which also works with Windows ``spawn``.
_progress_queue: Any = None
_cancel_event: Any = None
_blas_limits: Any = None


def init_worker(progress_queue: Any, cancel_event: Any, blas_threads: int | None) -> None:
    """
    ProcessPoolExecutor initializer, run once in every worker process.

    Args:
        progress_queue: Queue receiving ``(file_path, done, total)`` tuples.
        cancel_event: Event-like object (``is_set``) shared with the coordinator.
        blas_threads: Cap for BLAS/OpenMP threads in this process (None = no cap).
    """
    global _progress_queue, _cancel_event, _blas_limits
    _progress_queue = progress_queue
    _cancel_event = cancel_event
    if blas_threads is not None:
        try:
            from threadpoolctl import threadpool_limits

            _blas_limits = threadpool_limits(limits=blas_threads)
        except ImportError:  # pragma: no cover - threadpoolctl is a declared dependency
            _blas_limits = None


def reset_worker_state() -> None:
    """Undo ``init_worker`` (restores BLAS limits and drops the shared handles)."""
    global _progress_queue, _cancel_event, _blas_limits
    if _blas_limits is not None:
        _blas_limits.restore_original_limits()
    _progress_queue = None
    _cancel_event = None
    _blas_limits = None


def is_cancel_requested() -> bool:
    """True when the coordinator has signalled cancellation to this worker."""
    return _cancel_event is not None and _cancel_event.is_set()


def report_slice(file_path: str, done: int, total: int) -> None:
    """Send one per-slice progress message to the coordinator (no-op without a queue)."""
    if _progress_queue is not None:
        _progress_queue.put((file_path, done, total))


def export_one_file(
    file_path: str,
    params: SliceExportParams,
    config: ExportConfig,
) -> ExportResult:
    """
    Export a single OCT file in isolation and return a picklable result.

    This is the unit of work submitted to a process pool. It must not raise:
    any failure is captured into the returned ``ExportResult.error`` so the
    coordinator can keep processing the remaining files. Progress is reported
    after every slice and the shared cancel event is honoured between slices.

    Args:
        file_path: Path to the OCT file to export.
        params: Per-file slice export parameters.
        config: Export configuration.

    Returns:
        ExportResult with exported file paths (as strings), a failed-slice
        count, a ``cancelled`` flag, and an optional error message.
    """
    if is_cancel_requested():
        return ExportResult(file_path=file_path, cancelled=True)

    service = ExportService()
    try:
        return service.run_export(
            file_path,
            params,
            config,
            slice_callback=lambda done, total: report_slice(file_path, done, total),
            should_cancel=is_cancel_requested,
        )
    except Exception as exc:  # noqa: BLE001 - must never crash the worker
        return ExportResult(
            file_path=file_path,
            exported_files=[],
            failed_count=params.num_slices,
            error=f"{exc}\n{traceback.format_exc()}",
        )
