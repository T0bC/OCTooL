"""
ScanAlign Matching Service.

Pure index arithmetic for linked scrolling of two stacks with a fixed slice
offset. Later phases add the slice-matching logic here.

Key contents:
- compute_offset: Slice offset between the current positions of two stacks.
- linked_index: Maps a position in one stack to the linked position in the other.

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


def compute_offset(index1: int, index2: int) -> int:
    """Offset (delta) between two 0-based positions: ``index2 - index1``."""
    return index2 - index1


def linked_index(
    source_index: int, offset: int, target_count: int, source_is_scan1: bool
) -> tuple[int, bool]:
    """Map a position in the source stack to the linked position in the other stack.

    Scan 1 -> Scan 2 adds ``offset``; Scan 2 -> Scan 1 subtracts it. The result is
    clamped to ``[0, target_count - 1]``; the offset itself is never altered.

    Returns:
        ``(clamped_target, in_range)`` where ``in_range`` is False if clamping happened.
    """
    target = source_index + offset if source_is_scan1 else source_index - offset
    if target_count <= 0:
        return 0, False
    clamped = max(0, min(target, target_count - 1))
    return clamped, clamped == target
