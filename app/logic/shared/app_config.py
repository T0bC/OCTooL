#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application Configuration.

Version string and remote resource locations. Single source of truth for the OCTooL version and all server-hosted resources (documentation, changelog, update manifest). Edit the values here on every release or when moving server endpoints.

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



# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
# Bump this on every release. Keep it as a plain comparable string, e.g.
# "2026.2" or "2026.10". This is the canonical version used everywhere.
__version__ = "2026.5"

# Human-readable form shown in the window title / About dialog.
VERSION_DISPLAY = f" [v. {__version__}]"

# ---------------------------------------------------------------------------
# Remote resources (served by nginx on the Ubuntu server)
# ---------------------------------------------------------------------------
# Base URL of the OCTooL section on the web server. The trailing slash matters.
SERVER_BASE_URL = "https://dentlab.medizin.uni-leipzig.de/octool/"

# Live documentation. These always reflect the latest pushed HTML on the server,
# regardless of which app version the user has installed.
MANUAL_URL = SERVER_BASE_URL + "OCTooL_MANUAL.html"
CHANGELOG_URL = SERVER_BASE_URL + "OCTooL_change_log.html"

# Update manifest. A small JSON file the app polls to detect newer releases.
# Expected shape:
#   {
#     "version": "2026.3",
#     "download_url": "https://.../octool/downloads/OCTooL_2026.3.zip",
#     "changelog_url": "https://.../octool/OCTooL_change_log.html",
#     "notes": "Optional short message."
#   }
VERSION_MANIFEST_URL = SERVER_BASE_URL + "version.json"

# Network timeout (seconds) for the version check / doc reachability probe.
NETWORK_TIMEOUT = 5
