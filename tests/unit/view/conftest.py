"""
Shared fixtures for view tests.

Key contents:
- tk_root: One hidden Tk root for the whole test session.

ttkbootstrap keeps a global Style bound to the first Tk root it sees. If a test
module destroys its own root, the next module's widgets fail with "application has
been destroyed" (or the next root cannot be created), depending on test order. One
session-wide root avoids that.

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

import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def tk_root():
    """One hidden Tk root shared by all view tests (skipped without a display)."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    yield root
    root.destroy()
