"""
ScanAlign Matching Service.

Pure index arithmetic for linked scrolling of two stacks (fixed slice offset or
first/last ranges) and for choosing the N equidistant slice pairs to export.
All indices are 0-based positions in ``stack.files``.

Key contents:
- compute_offset: Slice offset between the current positions of two stacks.
- linked_index: Maps a position in one stack to the linked position in the other.
- max_pairs: Largest N the two ranges allow.
- pair_indices: N equidistant (index1, index2) position pairs of two ranges.
- build_pairs: SlicePair list including the '#' numbers used in output names.
- range_summary: (offset, scale) of two ranges.
- range_linked_index: Linked position derived from the two ranges (linear mapping).

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

from app.logic.scanalign.models import SlicePair, SliceRange, StackInfo
from app.logic.shared.slice_math import equidistant_indices


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


def max_pairs(r1: SliceRange, r2: SliceRange) -> int:
    """Largest number of pairs the two ranges allow (the shorter range length)."""
    return min(r1.length, r2.length)


def pair_indices(r1: SliceRange, r2: SliceRange, n: int) -> list[tuple[int, int]]:
    """N equidistant ``(index1, index2)`` 0-based position pairs of the two ranges.

    Raises:
        ValueError: unless ``2 <= n <= max_pairs(r1, r2)``.
    """
    limit = max_pairs(r1, r2)
    if n < 2 or n > limit:
        raise ValueError(f"Number of pairs must be between 2 and {limit}, got {n}")
    idx1 = [i - 1 for i in equidistant_indices(r1.first + 1, r1.last + 1, n)]
    idx2 = [i - 1 for i in equidistant_indices(r2.first + 1, r2.last + 1, n)]
    return list(zip(idx1, idx2, strict=True))


def _slice_number(stack: StackInfo, index: int) -> int:
    number = stack.files[index].slice_number
    return number if number is not None else index + 1


def build_pairs(
    stack1: StackInfo, stack2: StackInfo, r1: SliceRange, r2: SliceRange, n: int
) -> list[SlicePair]:
    """Build the ``SlicePair`` list (``k`` 1-based) for ``n`` pairs."""
    return [
        SlicePair(
            k=k,
            index1=i1,
            index2=i2,
            slice1=_slice_number(stack1, i1),
            slice2=_slice_number(stack2, i2),
        )
        for k, (i1, i2) in enumerate(pair_indices(r1, r2, n), start=1)
    ]


def range_summary(r1: SliceRange, r2: SliceRange) -> tuple[int, float]:
    """``(offset, scale)``: offset = ``r2.first - r1.first``, scale = ``len2 / len1``."""
    return r2.first - r1.first, r2.length / r1.length


def range_linked_index(
    source_index: int, src: SliceRange, tgt: SliceRange, target_count: int
) -> tuple[int, bool]:
    """Map a source position to the target position by linear range mapping.

    ``first`` maps to ``first`` and ``last`` to ``last``; positions outside the
    range are extrapolated. The result is rounded and clamped to
    ``[0, target_count - 1]``.

    Returns:
        ``(clamped_target, in_range)`` where ``in_range`` is False if clamping happened.
    """
    ratio = (tgt.last - tgt.first) / (src.last - src.first)
    target = round(tgt.first + (source_index - src.first) * ratio)
    if target_count <= 0:
        return 0, False
    clamped = max(0, min(target, target_count - 1))
    return clamped, clamped == target
