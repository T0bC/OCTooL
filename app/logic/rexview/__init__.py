"""
RexView Logic Package.

Contains business logic for OCT image export and preview functionality.

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


from app.logic.rexview.models import (
    ExportConfig,
    SliceExportParams,
    ExportProgress,
    ImageDisplayConfig,
    SettingsConfig,
    QueueItem,
    FileMetadata,
    ExportSettings,
    ExportResult,
)
from app.logic.rexview.validation import ValidationResult
from app.logic.rexview.export_service import ExportService
from app.logic.rexview.export_worker import export_one_file
from app.logic.rexview.parallel_export import ParallelExportCoordinator
from app.logic.rexview.image_service import ImageService
from app.logic.rexview.settings_service import SettingsService
from app.logic.rexview.queue_service import QueueService
from app.logic.rexview.file_discovery_service import FileDiscoveryService, DiscoveryResult

__all__ = [
    # Models
    'ExportConfig', 
    'SliceExportParams', 
    'ExportProgress', 
    'ImageDisplayConfig',
    'SettingsConfig',
    'QueueItem',
    'FileMetadata',
    'ExportSettings',
    'ExportResult',
    # Services
    'ExportService',
    'export_one_file',
    'ParallelExportCoordinator',
    'ImageService',
    'SettingsService',
    'QueueService',
    'FileDiscoveryService',
    # Results
    'ValidationResult',
    'DiscoveryResult',
]
