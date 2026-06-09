"""
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

from app.view.rexview.tree_view_panel import treeViewPanel
from app.view.rexview.pick_files_panel import pickFilesPanel
from app.view.rexview.global_settings_panel import globalSettingsPanel
from app.view.rexview.custom_settings_panel import customSettingsPanel
from app.view.rexview.image_panel import imagePanel
from app.view.rexview.execution_panel import executionPanel
from app.view.rexview.instruction_panel import instructionPanel

__all__ = [
    "treeViewPanel",
    "pickFilesPanel",
    "globalSettingsPanel",
    "customSettingsPanel",
    "imagePanel",
    "executionPanel",
    "instructionPanel",
]
