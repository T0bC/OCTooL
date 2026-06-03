"""
AnnoLyze UI panels.

Thin tkinter wrappers that delegate business logic to ``app.logic.annolyze``.
Submodules are imported directly by ``annoLyzeTab`` to avoid eager import of
heavy GUI dependencies at package import time.
"""
