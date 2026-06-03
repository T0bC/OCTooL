# RexView Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **logic extracted, panels moved, and Phase F view-layer cleanup complete — every `app/view/rexview/` file now contains only UI code (widgets/events) or thin service delegation.**

---

## Services & Models (in `app/logic/rexview/`)

| File | Status |
|------|--------|
| `export_service.py` | Done |
| `image_service.py` | Done |
| `settings_service.py` | Done |
| `queue_service.py` | Done |
| `file_discovery_service.py` | Done |
| `models.py` (ExportConfig, SliceExportParams, ImageDisplayConfig, SettingsConfig, QueueItem, FileMetadata, ExportSettings) | Done |

## Panels wired & moved to `app/view/rexview/`

- [x] `execution_panel.py` → ExportService
- [x] `image_panel.py` → ImageService
- [x] `global_settings_panel.py` → SettingsService
- [x] `custom_settings_panel.py` → SettingsService
- [x] `tree_view_panel.py` → QueueService
- [x] `pick_files_panel.py` → FileDiscoveryService
- [x] `instruction_panel.py` (static)
- [x] Imports updated in `rexViewTab.py`; old `RexView/` folder removed

## Tests

- [x] Unit: export (65+), image (36), settings (45+), queue (30+), file discovery (35+)
- [x] Integration: export pipeline (13)
- Total: 265 passing

---

## Phase F: View-Layer Cleanup (COMPLETE)

Audit found stale pure-logic methods and ad-hoc dialogs still in the view layer.

### F.1 Shared dialog helper
- [x] Create `app/view/shared/dialogs.py` (`show_error`/`show_info`/`show_warning` reusing root via `parent=`).

### F.2 `pick_files_panel.py` (reference cleanup)

| Method | Lines | Category | Action |
|--------|-------|----------|--------|
| `parse_metadata_file` | 275-387 | Pure logic, duplicated in `FileDiscoveryService` | **Delete** (only service tests reference it) |
| `handle_metadata_parsing` | 421-462 | Dead adapter (no external callers) | **Delete** |
| `show_error_box` | 390-413 | UI, spawns new `tk.Tk()` | **Remove**, route to `dialogs.show_error` |
| `show_info_box` | 415-419 | UI, spawns new `tk.Tk()` | **Remove**, route to `dialogs.show_info` |
| `_collect_oct_files`, `_build_entries_for_file` | — | Correct thin delegators | Keep |
| `globalPicker`, `globalPickerThread`, progress popups, `breakAll` | — | UI-only | Keep |

- [x] Delete `parse_metadata_file` and `handle_metadata_parsing` (verified no callers).
- [x] Replace dialog calls with `dialogs.show_error/show_info(self.root, ...)`.
- [x] Migrate `tree_view_panel.py` messageboxes to `dialogs`.
- [x] All tests pass (`pytest tests/`).

### F.3 Audit remaining panels (per-panel checklist in REFACTOR-PLAN.md)
- [x] `execution_panel.py` — collapsed duplicated inline pipeline in `mainRoutines` to a single `ExportService.run_export()` call (view now only iterates rows, runs `_collect_*` collectors, and translates `ExportProgress` → TreeView status). Wired `breakAll` → `export_service.cancel()` (+ `reset()` on start). Deleted dead `addExifToImage` and unused imports (`np`, `ndimage`, `Image`, `octF`, `gc`, `traceback`, `Path`, `OCTMetadata`, `ExportProgress`). Status text preserved exactly (`loading`, raw load index, `exp: N`, `Done`/`Done (N failed)`).
- [x] `image_panel.py` — removed stale view-layer state from `dispImageInCanvas`: dropped leaky `self.archive = self.image_service._archive` (private-member access), unused `self.xmlDict`, and dead `self.dBmin`/`self.dBmax` (already carried via `_collect_display_config` → `db_min`/`db_max`). Demoted `self.file` to a local `file_path`. View now only orchestrates widgets + service calls; no logic/data leftovers.
- [x] `global_settings_panel.py` — pure UI: widget construction + thin state getters (`getResizeState`, `getExpFormat`, etc.) + `_collect_settings_config`. No logic.
- [x] `custom_settings_panel.py` — pure UI: widgets + getters + `_collect_settings_config`; validation/parsing methods are thin delegators to `SettingsService`. Deleted dead `getEbenenState` (referenced never-created `self.expBox`, no callers).
- [x] `tree_view_panel.py` — UI: manipulates the `ttk.Treeview` widget; logic delegated to `QueueService` (`_collect_queue_item_from_row`, validations), messaging via `dialogs`. No standalone logic.
- [x] `instruction_panel.py` — static UI only, no logic.

### F.4 Enforce the boundary
- [x] Add import-safety test (`tests/unit/logic/test_rexview_import_safety.py`): `app/logic/rexview/*` imports with no tkinter, and source files contain no `import tkinter`.

### F.5 Robustness fixes (added during Phase F)
- [x] Global Tk exception handler: `install_tk_exception_handler(root)` in `utils/error_handler.py`, wired in `MainGui.__init__` so undecorated callbacks/lambdas surface a popup + log instead of failing silently.
- [x] Fixed AppContext key collision: RexView image keys namespaced to `rex_image`, AnnoLyze to `anno_image` (CarlQuant already used `carl_*`). This fixed the `Show` button calling an AnnoLyze panel.

---

## Completion Criteria

- [ ] Fully functional (manual GUI verification)
- [ ] 90%+ coverage on `app/logic/rexview/`
- [x] Fully separated — stale logic removed from `pick_files_panel.py`
- [x] Standalone testable (`pytest tests/unit/logic/test_rexview_*.py` runs without tkinter)
- [x] No ad-hoc dialogs (all via `app/view/shared/dialogs.py`)
