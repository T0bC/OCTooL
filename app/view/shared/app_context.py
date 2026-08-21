# -*- coding: utf-8 -*-
"""
Application Context.

Central registry for panels, frames, and the status bar. Provides safe,
thread-aware status updates so background workers can post messages without
calling Tkinter directly.

Also tracks background executors and timers created by panels, cancelling
them (and any pending Tk ``after()`` callback) on application exit, so a
leftover non-daemon thread or stale callback doesn't hang or corrupt state
on the next same-interpreter launch (e.g. IPython's %run).

Key contents:
- AppContext: Registry holding references to panels, frames, and config manager.
- register_panel / get_panel: Named panel registration and lookup.
- register_frame / get_frame: Named frame registration and lookup.
- safe_status_update: Thread-safe status-bar message dispatch.
- register_executor / register_timer / shutdown: Track and cleanly stop
  background work and pending Tk callbacks.
- silence_tcl_background_errors: Last-resort suppression of post-destroy Tcl
  background errors.

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



class AppContext:
    def __init__(self):
        self.root = None
        self.panels = {}
        self.frames = {}
        self.config_manager = None
        self._executors = []
        self._timers = []

    def register_panel(self, name: str, panel):
        self.panels[name] = panel

    def get_panel(self, name: str, required=True):
        panel = self.panels.get(name)
        if required and panel is None:
            raise ValueError(f"Panel '{name}' not found in context.")
        return panel

    def register_frame(self, name: str, frame):
        self.frames[name] = frame

    def get_frame(self, name: str):
        return self.frames.get(name)

    def safe_status_update(self, message: str, level: str = "info", duration: int = 2000):
        if getattr(self, "status_bar", None) is None:
            return

        target = self.status_bar
        widget = getattr(target, "frame", None) or getattr(target, "label", None)
        if widget is None:
            target.update(message, level, duration)
            return

        widget.after(0, lambda: target.update(message, level, duration))

    def register_executor(self, executor):
        """Track a ThreadPoolExecutor/ProcessPoolExecutor so shutdown() stops
        it on exit -- non-daemon executor threads otherwise block interpreter
        shutdown if the window closes while one is still running."""
        self._executors.append(executor)

    def register_timer(self, timer, on_pending=None):
        """Track a threading.Timer (e.g. debounced autosave) for cancellation
        on exit. ``on_pending``, if given, runs immediately instead of losing
        the timer's work when it was still pending at shutdown."""
        self._timers.append((timer, on_pending))

    def shutdown(self, wait_seconds: float = 5.0):
        """Stop all tracked background work before the application exits.
        Pending timers run their on_pending callback then get cancelled.
        Each executor is shut down with queued work cancelled; a task already
        running gets up to wait_seconds to finish so Quit stays responsive
        without killing normal work mid-write."""
        for timer, on_pending in self._timers:
            if timer.is_alive():
                timer.cancel()
                if on_pending is not None:
                    try:
                        on_pending()
                    except Exception:
                        pass
        self._timers.clear()

        for executor in self._executors:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
                # ThreadPoolExecutor.shutdown() has no timeout; join its
                # worker threads ourselves so a stuck task can't hang exit.
                for thread in list(getattr(executor, "_threads", [])):
                    thread.join(timeout=wait_seconds)
            except Exception:
                pass
        self._executors.clear()

        self._cancel_pending_after_jobs()

    def _cancel_pending_after_jobs(self):
        """Cancel every after() callback still queued on the root's Tcl
        interpreter, so none fire post-destroy and corrupt state for a
        same-interpreter rerun (e.g. IPython's %run)."""
        root = self.root
        if root is None:
            return
        try:
            pending_ids = root.tk.call('after', 'info')
        except Exception:
            return
        for after_id in pending_ids:
            try:
                root.after_cancel(after_id)
            except Exception:
                pass

    def silence_tcl_background_errors(self):
        """Replace Tcl's bgerror handler with a no-op just before the root is
        destroyed. Closes the residual race where a background thread queues
        an after() callback after _cancel_pending_after_jobs already drained
        the queue; such a callback fires mid-teardown and Tcl reports it via
        bgerror, which can corrupt state for the next same-interpreter run."""
        root = self.root
        if root is None:
            return
        try:
            root.tk.call('proc', 'bgerror', 'msg', '')
        except Exception:
            pass
