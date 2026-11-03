"""
Slice Math.

Pure helpers for choosing slice indices, shared by RexView and ScanAlign
(no tkinter dependencies).

Key contents:
- equidistant_indices: Evenly spaced slice numbers within a 1-based range.

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


def equidistant_indices(first: int, last: int, n: int) -> list[int]:
    """
    Calculate equidistant slice indices within a range.

    Args:
        first: First slice number (1-indexed)
        last: Last slice number (1-indexed)
        n: Number of equidistant slices to calculate

    Returns:
        List of slice indices (1-indexed)
    """
    if n <= 0:
        return []

    if n == 1:
        return [(first + last) // 2]

    total_range = last - first
    if n > total_range + 1:
        # More slices requested than available, return all
        return list(range(first, last + 1))

    step = total_range / (n - 1)
    return [round(first + i * step) for i in range(n)]
