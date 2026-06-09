"""
RexView Parallel Export Coordinator.

Pure business logic (no tkinter) that distributes per-file OCT exports across
multiple processes using a ProcessPoolExecutor. Each file is an independent
unit of CPU-bound work, so file-level parallelism scales well with low
overhead. The coordinator is fully unit-testable: the executor factory and the
worker function are injectable, so tests can run synchronously without spawning
real processes.

Key contents:
- ParallelExportCoordinator: Distributes per-file exports across a process pool.
- compute_worker_count: Determines workers capped by CPU, queue length, and RAM.
- run: Submits tasks to the executor and collects ExportResults with progress.

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

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Iterable, List, Optional, Tuple

from app.logic.rexview.models import ExportConfig, SliceExportParams, ExportResult
from app.logic.rexview.export_worker import export_one_file

# A task is a (file_path, params, config) tuple dispatched to a worker.
ExportTask = Tuple[str, SliceExportParams, ExportConfig]


class ParallelExportCoordinator:
    """Coordinate process-parallel export of multiple OCT files."""

    #: Hard upper bound on worker processes regardless of CPU count.
    DEFAULT_MAX_WORKERS_CAP = 8

    def __init__(
        self,
        worker_fn: Callable[..., ExportResult] = export_one_file,
        executor_factory: Callable[..., object] = ProcessPoolExecutor,
        cpu_count: Optional[int] = None,
        max_workers_cap: Optional[int] = None,
        available_memory_gb: Optional[float] = None,
        gb_per_worker: Optional[float] = None,
    ):
        """
        Args:
            worker_fn: Top-level, picklable callable invoked per file.
            executor_factory: Callable returning a context-manager executor with
                a ``submit`` method (defaults to ``ProcessPoolExecutor``).
            cpu_count: Override for the detected CPU count (mainly for tests).
            max_workers_cap: Hard cap on worker processes.
            available_memory_gb: Optional available RAM budget in GiB. When given
                together with ``gb_per_worker``, the worker count is additionally
                capped so the pool does not exhaust memory (raw-spectral exports
                hold large arrays per process).
            gb_per_worker: Estimated peak RAM per worker process in GiB.
        """
        self._worker_fn = worker_fn
        self._executor_factory = executor_factory
        self._cpu_count = cpu_count
        self._max_workers_cap = max_workers_cap or self.DEFAULT_MAX_WORKERS_CAP
        self._available_memory_gb = available_memory_gb
        self._gb_per_worker = gb_per_worker
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the coordinator to stop submitting further tasks."""
        self._cancelled = True

    def reset(self) -> None:
        """Clear the cancellation flag for reuse."""
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def compute_worker_count(
        self,
        queue_len: int,
        requested: Optional[int] = None,
    ) -> int:
        """
        Determine the number of worker processes to use.

        Defaults to ``cpu_count - 1`` (leaving a core for the UI), bounded by the
        queue length and a hard cap. An explicit ``requested`` value overrides the
        CPU-based default but is still clamped to ``[1, cap]`` and the queue length.
        """
        cpu = self._cpu_count if self._cpu_count is not None else (os.cpu_count() or 1)
        base = requested if requested is not None else max(cpu - 1, 1)
        bounded = min(base, self._max_workers_cap)
        if queue_len > 0:
            bounded = min(bounded, queue_len)
        if self._available_memory_gb is not None and self._gb_per_worker:
            mem_workers = int(self._available_memory_gb // self._gb_per_worker)
            bounded = min(bounded, mem_workers)
        return max(1, bounded)

    def run(
        self,
        tasks: Iterable[ExportTask],
        worker_count: Optional[int] = None,
        progress_callback: Optional[Callable[[ExportResult], None]] = None,
    ) -> List[ExportResult]:
        """
        Execute all export tasks across a pool and collect their results.

        Args:
            tasks: Iterable of (file_path, params, config) tuples.
            worker_count: Optional explicit worker count override.
            progress_callback: Optional callback invoked with each ExportResult
                as it completes (called on the coordinator's thread).

        Returns:
            List of ExportResult objects (one per completed task).
        """
        tasks = list(tasks)
        results: List[ExportResult] = []

        if self._cancelled or not tasks:
            return results

        n_workers = self.compute_worker_count(len(tasks), worker_count)

        with self._executor_factory(max_workers=n_workers) as executor:
            future_to_task = {}
            for task in tasks:
                if self._cancelled:
                    break
                future = executor.submit(self._worker_fn, *task)
                future_to_task[future] = task

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                file_path = task[0]
                params = task[1]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - isolate worker failures
                    result = ExportResult(
                        file_path=file_path,
                        exported_files=[],
                        failed_count=getattr(params, 'num_slices', 0),
                        error=str(exc),
                    )
                results.append(result)
                if progress_callback:
                    progress_callback(result)

        return results
