#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application configuration: version and remote resource locations.

Single source of truth for the OCTooL version string and all server-hosted
resources (documentation, changelog, update manifest). Edit the values here
whenever you release a new version or move the server endpoints.

@author: Tobias Meissner
"""

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
# Bump this on every release. Keep it as a plain comparable string, e.g.
# "2026.2" or "2026.10". This is the canonical version used everywhere.
__version__ = "2026.2"

# Human-readable form shown in the window title / About dialog.
VERSION_DISPLAY = f" [v. {__version__}]"

# ---------------------------------------------------------------------------
# Remote resources (served by nginx on the Ubuntu server)
# ---------------------------------------------------------------------------
# Base URL of the OCTooL section on the web server. The trailing slash matters.
SERVER_BASE_URL = "https://dentlab.uni-leipzig.de/octool/"

# Live documentation. These always reflect the latest pushed HTML on the server,
# regardless of which app version the user has installed.
MANUAL_URL = SERVER_BASE_URL + "docs/latest/OCTooL_MANUAL.html"
CHANGELOG_URL = SERVER_BASE_URL + "docs/latest/OCTooL_change_log.html"

# Update manifest. A small JSON file the app polls to detect newer releases.
# Expected shape:
#   {
#     "version": "2026.3",
#     "download_url": "https://.../octool/downloads/OCTooL_2026.3.zip",
#     "changelog_url": "https://.../octool/docs/latest/OCTooL_change_log.html",
#     "notes": "Optional short message."
#   }
VERSION_MANIFEST_URL = SERVER_BASE_URL + "version.json"

# Network timeout (seconds) for the version check / doc reachability probe.
NETWORK_TIMEOUT = 5
