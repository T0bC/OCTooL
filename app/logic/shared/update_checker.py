#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update checker.

Fetches the version manifest (``version.json``) from the server and compares the
advertised version against the locally installed ``__version__``. Network access
runs on a background thread so the GUI never blocks, and any failure (offline,
DNS, timeout, malformed JSON) is swallowed silently in the automatic path.

Two entry points:
    * ``check_for_updates_async`` - non-blocking, used on startup. Calls back into
      the GUI thread only when a newer version is found.
    * ``check_for_updates_sync`` - blocking, used by the manual "Check for updates"
      button so the user always gets feedback (including "up to date" / errors).

@author: Tobias Meissner
"""

import json
import threading
import urllib.request

from app.logic.shared.app_config import (
    __version__,
    VERSION_MANIFEST_URL,
    NETWORK_TIMEOUT,
)


class UpdateInfo:
    """Result of an update check."""

    def __init__(self, available, latest_version=None, download_url=None,
                 changelog_url=None, notes=None, error=None):
        self.available = available
        self.latest_version = latest_version
        self.download_url = download_url
        self.changelog_url = changelog_url
        self.notes = notes
        self.error = error


def _parse_version(version_str):
    """Turn a version string like '2026.10' into a comparable tuple (2026, 10).

    Falls back to a string comparison tuple if the format is unexpected, so the
    comparison never raises.
    """
    try:
        return tuple(int(part) for part in str(version_str).strip().split("."))
    except (ValueError, AttributeError):
        return (str(version_str),)


def _is_newer(remote, local):
    """Return True if ``remote`` version is strictly newer than ``local``."""
    try:
        return _parse_version(remote) > _parse_version(local)
    except TypeError:
        # Mixed int/str tuples (malformed remote): compare as strings.
        return str(remote) != str(local)


def _fetch_manifest():
    """Download and parse the version manifest. Returns an :class:`UpdateInfo`."""
    try:
        req = urllib.request.Request(
            VERSION_MANIFEST_URL,
            headers={"User-Agent": f"OCTooL/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest = data.get("version")
        if not latest:
            return UpdateInfo(False, error="Manifest missing 'version' field.")

        return UpdateInfo(
            available=_is_newer(latest, __version__),
            latest_version=latest,
            download_url=data.get("download_url"),
            changelog_url=data.get("changelog_url"),
            notes=data.get("notes"),
        )
    except Exception as exc:  # offline, timeout, DNS, JSON error, etc.
        return UpdateInfo(False, error=str(exc))


def check_for_updates_sync():
    """Blocking check. Always returns an :class:`UpdateInfo` (never raises)."""
    return _fetch_manifest()


def check_for_updates_async(tk_widget, on_update_available, on_error=None):
    """Non-blocking check used at startup.

    Args:
        tk_widget: Any Tk widget, used to marshal the callback back onto the GUI
            thread via ``after`` (Tk is not thread-safe).
        on_update_available: Callable(UpdateInfo) invoked only when a newer
            version exists.
        on_error: Optional callable(UpdateInfo) invoked on failure. Defaults to
            silent (startup path).
    """

    def worker():
        info = _fetch_manifest()

        def dispatch():
            if info.available:
                on_update_available(info)
            elif info.error and on_error is not None:
                on_error(info)

        try:
            tk_widget.after(0, dispatch)
        except Exception:
            # Widget destroyed before the check finished; ignore.
            pass

    threading.Thread(target=worker, daemon=True).start()
