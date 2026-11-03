"""
ScanAlign Export Service.

Pure business logic (no tkinter) for exporting the matched slice pairs of two
scans into two self-contained folders: slice k of both folders shows the same
anatomy. Files are copied byte-for-byte; a JSON registration log is written last.

Key contents:
- output_folder_name / next_free_folder / output_file_name: Output naming contract.
- resolve_exp_number / resolve_name: Fallbacks for exp number and scan name.
- RegistrationExporter: Copies the pairs, writes the logs, cleans up on cancel/error
  (cancellation via the shared Cancellable mixin).

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

import re
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.logic.scanalign.matching_service import range_summary
from app.logic.scanalign.models import (
    ExportResult,
    GeometryComparison,
    RegistrationLog,
    RegistrationPairEntry,
    RegistrationScanInfo,
    SlicePair,
    SliceRange,
    StackInfo,
)
from app.logic.shared.app_config import __version__
from app.logic.shared.concurrency import Cancellable
from app.logic.shared.json_io import write_json_atomic

LOG_FILE_NAME = "scanalign_registration.json"
_LEADING_EXP_RE = re.compile(r"^(\d+)_")
_UNSAFE_PATH_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def output_folder_name(exp: int, name: str, n: int) -> str:
    """Base name of an output folder, e.g. ``01_010RI_ScanAlign_25``.

    ``name`` is the scan name (see ``resolve_name``); characters not allowed in Windows
    paths are replaced by ``_``, and an empty name is left out (``01_ScanAlign_25``).
    """
    safe = _UNSAFE_PATH_CHARS_RE.sub("_", name or "").strip(" .")
    middle = f"{safe}_" if safe else ""
    return f"{exp:02d}_{middle}ScanAlign_{n}"


def next_free_folder(parent: Path, base: str) -> str:
    """Return ``base``, ``base_2``, ``base_3`` ... - the first name not existing in ``parent``."""
    candidate = base
    counter = 2
    while (Path(parent) / candidate).exists():
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def output_file_name(name: str, exp: int, slice_no: int, k: int, ext: str) -> str:
    """RexView-compatible file name ``{name}_{exp}_#{slice}_{k:04d}{ext}``."""
    return f"{name}_{exp}_#{slice_no}_{k:04d}{ext}"


def resolve_exp_number(stack: StackInfo) -> int:
    """Exp number from the parsed file names, else the folder's leading digits, else 1."""
    if stack.exp_number is not None:
        return stack.exp_number
    match = _LEADING_EXP_RE.match(stack.folder.name)
    return int(match.group(1)) if match else 1


def resolve_name(stack: StackInfo) -> str:
    """Scan name from the parsed file names, else the specimen name."""
    return stack.name or stack.specimen


def _slice_number(stack: StackInfo, index: int) -> int:
    number = stack.files[index].slice_number
    return number if number is not None else index + 1


class RegistrationExporter(Cancellable):
    """Copies N slice pairs of two stacks into two new, self-contained folders."""

    def run(
        self,
        stack1: StackInfo,
        stack2: StackInfo,
        r1: SliceRange,
        r2: SliceRange,
        pairs: list[SlicePair],
        comparison: GeometryComparison,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> ExportResult:
        """Export the pairs; returns ``cancelled=True`` (and no folders) if cancelled.

        Raises:
            ValueError: if a source file no longer exists (nothing is created).
        """
        stacks = (stack1, stack2)
        sources = (
            [stack1.files[p.index1].path for p in pairs],
            [stack2.files[p.index2].path for p in pairs],
        )
        missing = [p for column in sources for p in column if not p.is_file()]
        if missing:
            raise ValueError(
                f"{len(missing)} source file(s) no longer exist (was the export deleted "
                f"or moved?), e.g. {missing[0]}"
            )

        n = len(pairs)
        created: list[Path] = []
        try:
            folders = (
                self._claim_folder(stack1, n, created),
                self._claim_folder(stack2, n, created),
            )
            slice_numbers = ([p.slice1 for p in pairs], [p.slice2 for p in pairs])
            names = [
                [
                    output_file_name(
                        resolve_name(stack),
                        resolve_exp_number(stack),
                        slice_no,
                        pair.k,
                        src.suffix,
                    )
                    for pair, slice_no, src in zip(pairs, slice_nos, column, strict=True)
                ]
                for stack, slice_nos, column in zip(stacks, slice_numbers, sources, strict=True)
            ]

            total = 2 * n
            done = 0
            if on_progress:
                on_progress(0, total)
            for column in (0, 1):
                for row, src in enumerate(sources[column]):
                    if self.is_cancelled:
                        self._cleanup(created)
                        return ExportResult(folders=folders, n_files=0, cancelled=True)
                    shutil.copy2(src, folders[column] / names[column][row])
                    done += 1
                    if on_progress:
                        on_progress(done, total)

            if self.is_cancelled:
                self._cleanup(created)
                return ExportResult(folders=folders, n_files=0, cancelled=True)

            for role, folder in (("reference", folders[0]), ("moving", folders[1])):
                log = self._build_log(role, stacks, (r1, r2), pairs, comparison, folders, names)
                write_json_atomic(folder / LOG_FILE_NAME, log.model_dump(mode="json"))
            return ExportResult(folders=folders, n_files=total, cancelled=False)
        except BaseException:
            self._cleanup(created)
            raise

    @staticmethod
    def _claim_folder(stack: StackInfo, n: int, created: list[Path]) -> Path:
        """Create a fresh output folder next to the export; never reuse an existing one."""
        parent = stack.folder.parent
        base = output_folder_name(resolve_exp_number(stack), resolve_name(stack), n)
        while True:
            folder = parent / next_free_folder(parent, base)
            try:
                folder.mkdir(exist_ok=False)
            except FileExistsError:
                continue
            created.append(folder)
            return folder

    @staticmethod
    def _cleanup(created: list[Path]) -> None:
        """Remove only the folders this run created."""
        for folder in created:
            shutil.rmtree(folder, ignore_errors=True)

    @staticmethod
    def _scan_info(stack: StackInfo, rng: SliceRange, folder: Path) -> RegistrationScanInfo:
        return RegistrationScanInfo(
            source_folder=stack.folder,
            oct_path=stack.geometry.oct_path,
            specimen=stack.specimen,
            name=stack.name,
            exp=resolve_exp_number(stack),
            n_slices=len(stack.files),
            geometry=stack.geometry,
            warnings=list(stack.warnings),
            range_positions=(rng.first, rng.last),
            range_slice_numbers=(
                _slice_number(stack, rng.first),
                _slice_number(stack, rng.last),
            ),
            output_folder=folder,
        )

    def _build_log(
        self,
        role: str,
        stacks: tuple[StackInfo, StackInfo],
        ranges: tuple[SliceRange, SliceRange],
        pairs: list[SlicePair],
        comparison: GeometryComparison,
        folders: tuple[Path, Path],
        names: list[list[str]],
    ) -> RegistrationLog:
        own, other = (0, 1) if role == "reference" else (1, 0)
        offset, scale = range_summary(*ranges)
        entries = [
            RegistrationPairEntry(
                k=pair.k,
                slice1=pair.slice1,
                slice2=pair.slice2,
                source1=stacks[0].files[pair.index1].path.name,
                source2=stacks[1].files[pair.index2].path.name,
                output1=names[0][row],
                output2=names[1][row],
            )
            for row, pair in enumerate(pairs)
        ]
        return RegistrationLog(
            octool_version=__version__,
            created=datetime.now().astimezone().isoformat(timespec="seconds"),
            role=role,
            scan=self._scan_info(stacks[own], ranges[own], folders[own]),
            partner=self._scan_info(stacks[other], ranges[other], folders[other]),
            n=len(pairs),
            offset=offset,
            scale=scale,
            comparison=comparison,
            pairs=entries,
        )
