"""
ScanAlign instruction tests.

Checks that the ScanAlign getting-started guide exists in assets/instructions.json
and is wired into the help dialog's tab-to-key mapping.

Key contents:
- test_instructions_json_has_scanalign_guide: JSON entry exists and is well-formed.
- test_help_dialog_maps_scanalign_tab: HelpDialog tab type 3 resolves to the guide.

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

import pytest

from app.logic.shared.json_io import read_json
from app.logic.shared.paths import resource_path
from app.view.shared.help_dialog import HelpDialog

KEY = "scanalign_getting_started"


@pytest.mark.unit
def test_instructions_json_has_scanalign_guide():
    data = read_json(resource_path("assets/instructions.json"))
    assert KEY in data
    assert data[KEY]["layout"] == "comprehensive_guide"
    assert len(data[KEY]["workflow_steps"]) >= 1


@pytest.mark.unit
def test_help_dialog_maps_scanalign_tab():
    dialog = HelpDialog(None, None, 3)
    assert dialog.tab_to_instruction_key[3] == KEY
    assert KEY in dialog.instructions
