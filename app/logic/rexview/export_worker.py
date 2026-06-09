"""
RexView Export Worker.

Key contents:
- export_one_file: Top-level picklable worker that builds an ExportService and
  exports a single OCT file, capturing any failure into ExportResult.

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
        return service.run_export(file_path, params, config)
    except Exception as exc:  # noqa: BLE001 - must never crash the worker
        return ExportResult(
            file_path=file_path,
            exported_files=[],
            failed_count=params.num_slices,
            error=f"{exc}\n{traceback.format_exc()}",
        )
