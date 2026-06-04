"""
Resource path resolution (pure, tkinter-free).

Provides :func:`resource_path`, the canonical helper for resolving asset paths
in both development and PyInstaller-bundled environments.
"""
import sys
import os


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.

    When running as a PyInstaller bundle, files are in ``sys._MEIPASS``.
    When running as a normal script, files are relative to the project root.

    This module lives at ``app/logic/shared/paths.py`` (three packages deep),
    so deriving the project root requires walking up four directory levels:
    ``paths.py`` -> ``shared`` -> ``logic`` -> ``app`` -> project root.

    Args:
        relative_path: Path relative to the application root (e.g., 'icons/thumb_4.ico')

    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Running as normal Python script: walk up to the project root.
        base_path = os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
            )
        )

    return os.path.join(base_path, relative_path)
