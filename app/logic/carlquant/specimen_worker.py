"""
CarlQuant Specimen Worker.

Top-level, picklable entry point executed inside a ProcessPoolExecutor worker to
analyse one whole specimen (all of its slices) and persist the results to disc.

Batch runs parallelise at the *specimen* axis rather than the slice axis: a
specimen is typically only ~25 slices, which is far too small a unit to amortise
the cost of starting a process pool, while a run typically holds several hundred
specimens. Giving each worker a whole specimen means one long-lived pool for the
entire batch, and it keeps the heavy analysis results inside the worker -- they
are written straight to disc, so only a small SpecimenAnalysisResult is pickled
back to the parent process.

Key contents:
- analyze_specimen_worker: Analyse every slice of one specimen and save results.

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

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - avoids a heavy import in spawned workers
    from app.logic.carlquant.analysis_service import SpecimenAnalysisResult

# Forces AnalysisService.analyze_specimen down its sequential branch: the worker
# already *is* the unit of parallelism, so it must never open a nested pool.
_NO_NESTED_POOL = 10**9


def analyze_specimen_worker(
    specimen,
    num_sound: int,
    num_lesion: int,
    detection_method: str,
) -> SpecimenAnalysisResult:
    """Analyse every slice of ``specimen`` and save its results to disc.

    Runs in a worker process, so ``specimen`` is a private copy: mutations to it
    are not visible to the parent, and the returned
    :class:`SpecimenAnalysisResult` (a handful of scalars) is the only payload
    pickled back. ``specimen.status`` is carried on that result so the caller can
    apply it to its own copy.

    Args:
        specimen: The Specimen to analyse. Must already carry any UI-stamped
            metadata (``measurement``, ``operator``) -- the worker cannot reach
            back into the application context.
        num_sound: Number of sound regions to extract per slice.
        num_lesion: Number of lesion regions to extract per slice.
        detection_method: Lesion-depth detection method name.

    Returns:
        The :class:`SpecimenAnalysisResult` produced by
        :meth:`AnalysisService.analyze_specimen`.
    """
    # Imported here rather than at module scope so that merely importing this
    # module (which the parent does, to reference the function) stays cheap.
    from app.logic.carlquant.analysis_service import AnalysisService

    return AnalysisService.analyze_specimen(
        specimen,
        num_sound=num_sound,
        num_lesion=num_lesion,
        detection_method=detection_method,
        result_lock=None,  # the specimen copy is private to this process
        save=True,
        parallel_threshold=_NO_NESTED_POOL,
    )
