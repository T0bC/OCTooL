"""
Shared Concurrency Helpers.

Pure business logic (no tkinter) for the process-parallel coordinators and the
cancellable services: the worker-count policy, a stdlib-only available-RAM probe
and a small cancellation-flag mixin.

Key contents:
- detect_available_memory_gb: Stdlib-only available-RAM probe for the RAM cap.
- compute_worker_count: CPU/RAM/queue-bounded worker-count policy.
- Cancellable: Mixin providing cancel(), reset() and is_cancelled.

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
import sys


def detect_available_memory_gb() -> float | None:
    """Best-effort available-RAM probe in GiB, or None if it cannot be determined.

    Deliberately stdlib-only: ``psutil`` is not a declared dependency of OCTooL
    and adding one for a worker-count heuristic is not worth it. Any failure
    yields None, which simply disables the RAM cap.
    """
    try:
        if sys.platform == "win32":
            import ctypes

            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return status.ullAvailPhys / (1024**3)

        with open("/proc/meminfo") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024**2)
    except Exception:  # noqa: BLE001 - a probe must never break the analysis
        return None
    return None


def compute_worker_count(
    queue_len: int,
    requested: int | None = None,
    *,
    max_workers_cap: int,
    cpu_count: int | None = None,
    available_memory_gb: float | None = None,
    gb_per_worker: float | None = None,
) -> int:
    """Determine the number of worker processes for a queue of ``queue_len`` tasks.

    Defaults to ``cpu_count - 1`` (leaving a core for the UI), then bounds by a
    hard cap, the queue length and -- when both ``available_memory_gb`` and
    ``gb_per_worker`` are given -- a memory budget. An explicit ``requested``
    value replaces the CPU-based default but is still clamped. The result is
    never below 1. No memory probing happens here; callers decide whether to
    supply ``available_memory_gb``.
    """
    cpu = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    base = requested if requested is not None else max(cpu - 1, 1)
    bounded = min(base, max_workers_cap)
    if queue_len > 0:
        bounded = min(bounded, queue_len)
    if available_memory_gb is not None and gb_per_worker:
        bounded = min(bounded, int(available_memory_gb // gb_per_worker))
    return max(1, bounded)


class Cancellable:
    """Mixin providing a cooperative cancellation flag.

    The flag is a class-level default, so subclasses need not call
    ``super().__init__()``; the first ``cancel()`` creates the instance attribute.
    """

    _cancelled = False

    def cancel(self) -> None:
        """Signal the work to stop."""
        self._cancelled = True

    def reset(self) -> None:
        """Clear the cancellation flag for reuse."""
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled
