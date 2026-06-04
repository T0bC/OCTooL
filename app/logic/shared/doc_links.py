#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Documentation link opener.

Opens server-hosted documentation in the default browser, with a graceful
fallback to the locally bundled HTML copy when the server is unreachable
(offline use, server down, DNS failure, etc.).

The server copy is always preferred because it stays current regardless of the
installed app version; the bundled copy guarantees the docs remain available
without an internet connection.

@author: Tobias Meissner
"""

import os
import webbrowser
import urllib.request

from app.logic.shared.paths import resource_path
from app.logic.shared.app_config import NETWORK_TIMEOUT


def _url_reachable(url):
    """Quick reachability probe for the remote document. Never raises."""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "OCTooL"})
        with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
            return 200 <= getattr(resp, "status", resp.getcode()) < 400
    except Exception:
        return False


def _open_local(local_alternatives):
    """Open the first existing bundled HTML file. Returns True on success."""
    for rel_path in local_alternatives:
        try:
            candidate = resource_path(rel_path)
            if os.path.exists(candidate):
                webbrowser.open("file://" + os.path.abspath(candidate))
                return True
        except Exception:
            continue
    return False


def open_doc(url, local_alternatives):
    """Open documentation, preferring the server URL with an offline fallback.

    Args:
        url: The server-hosted document URL.
        local_alternatives: Ordered list of project-relative paths to the
            bundled HTML copies, tried if the server is unreachable.

    Returns:
        True if either the remote or a local copy was opened, else False.
    """
    if _url_reachable(url):
        webbrowser.open(url)
        return True

    return _open_local(local_alternatives)
