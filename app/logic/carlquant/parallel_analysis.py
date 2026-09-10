"""
CarlQuant Parallel Specimen Coordinator.

Pure business logic (no tkinter) that distributes whole-specimen analyses across
multiple processes using a single, long-lived ProcessPoolExecutor.

Parallelism is at the *specimen* axis. A specimen is typically ~25 slices, which
is too small a unit to amortise process-pool startup -- and under the ``spawn``
start method used on Windows and macOS, starting a pool per specimen makes
startup dominate a batch run. A typical run holds several hundred specimens, so
one pool for the whole batch with one specimen per task keeps the workers busy
and pays startup exactly once. Each worker saves its own results to disc, so no
bulk analysis data crosses the process boundary.

The coordinator is fully unit-testable: the executor factory and the worker
function are injectable, so tests can run synchronously without spawning real
processes.

Key contents:
- ParallelSpecimenCoordinator: Distributes per-specimen analyses across a pool.
- run: Submits one task per specimen and collects results with progress.

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
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed

from app.logic.carlquant.analysis_service import SpecimenAnalysisResult
from app.logic.carlquant.specimen_worker import analyze_specimen_worker


class ParallelSpecimenCoordinator:
    """Coordinate process-parallel analysis of multiple specimens."""

    #: Hard upper bound on worker processes regardless of CPU count.
    DEFAULT_MAX_WORKERS_CAP = 8

    #: Rough peak RAM per worker in GiB. A worker holds one specimen's full
    #: results (dominated by LesionDepth.lesion_detection_data) until it saves.
    DEFAULT_GB_PER_WORKER = 1.5

    def __init__(
        self,
        worker_fn: Callable[..., SpecimenAnalysisResult] = analyze_specimen_worker,
        executor_factory: Callable[..., object] = ProcessPoolExecutor,
        cpu_count: int | None = None,
        max_workers_cap: int | None = None,
        available_memory_gb: float | None = None,
        gb_per_worker: float | None = None,
    ):
        """
        Args:
            worker_fn: Top-level, picklable callable invoked per specimen.
            executor_factory: Callable returning a context-manager executor with
                a ``submit`` method (defaults to ``ProcessPoolExecutor``).
            cpu_count: Override for the detected CPU count (mainly for tests).
            max_workers_cap: Hard cap on worker processes.
            available_memory_gb: Optional available RAM budget in GiB. When given
                together with ``gb_per_worker``, the worker count is additionally
                capped so the pool does not exhaust memory.
            gb_per_worker: Estimated peak RAM per worker process in GiB.
        """
        self._worker_fn = worker_fn
        self._executor_factory = executor_factory
        self._cpu_count = cpu_count
        self._max_workers_cap = max_workers_cap or self.DEFAULT_MAX_WORKERS_CAP
        self._available_memory_gb = available_memory_gb
        self._gb_per_worker = gb_per_worker or self.DEFAULT_GB_PER_WORKER
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the coordinator to stop submitting further specimens."""
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
        requested: int | None = None,
    ) -> int:
        """
        Determine the number of worker processes to use.

        Mirrors the policy of
        :meth:`app.logic.rexview.parallel_export.ParallelExportCoordinator.compute_worker_count`:
        defaults to ``cpu_count - 1`` (leaving a core for the UI), bounded by the
        queue length, a hard cap, and an optional RAM budget. An explicit
        ``requested`` value overrides the CPU-based default but is still clamped.
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
        specimens: Iterable,
        *,
        num_sound: int,
        num_lesion: int,
        detection_method: str,
        worker_count: int | None = None,
        on_mode: Callable[[str, int], None] | None = None,
        progress_callback: Callable[[SpecimenAnalysisResult], None] | None = None,
    ) -> list[SpecimenAnalysisResult]:
        """
        Analyse all specimens across a single pool and collect their results.

        Args:
            specimens: Iterable of Specimen objects. Each must already carry any
                UI-stamped metadata, since workers cannot reach the app context.
            num_sound: Number of sound regions to extract per slice.
            num_lesion: Number of lesion regions to extract per slice.
            detection_method: Lesion-depth detection method name.
            worker_count: Optional explicit worker count override.
            on_mode: Optional ``(mode, workers)`` hook invoked once, before work
                starts, reporting the pool size for the whole batch.
            progress_callback: Optional callback invoked with each
                SpecimenAnalysisResult as it completes (called on the
                coordinator's thread).

        Returns:
            List of SpecimenAnalysisResult objects, in completion order.
        """
        specimens = list(specimens)
        results: list[SpecimenAnalysisResult] = []

        if self._cancelled or not specimens:
            return results

        n_workers = self.compute_worker_count(len(specimens), worker_count)
        if on_mode is not None:
            on_mode("parallel" if n_workers > 1 else "sequential", n_workers)

        with self._executor_factory(max_workers=n_workers) as executor:
            future_to_specimen = {}
            for specimen in specimens:
                if self._cancelled:
                    break
                future = executor.submit(
                    self._worker_fn,
                    specimen,
                    num_sound,
                    num_lesion,
                    detection_method,
                )
                future_to_specimen[future] = specimen

            if self._cancelled:
                # Drop anything that has not started; in-flight work still
                # completes and is collected below.
                for future in future_to_specimen:
                    future.cancel()

            for future in as_completed(future_to_specimen):
                specimen = future_to_specimen[future]
                if future.cancelled():
                    continue
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - isolate worker failures
                    result = SpecimenAnalysisResult(
                        specimen_id=getattr(specimen, "specimen_id", "?"),
                        status=f"Error: {exc}",
                        processed_count=0,
                        total_slices=getattr(specimen, "slices", 0),
                        saved=False,
                    )
                results.append(result)
                if progress_callback is not None:
                    progress_callback(result)

        return results
