# RexView Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **logic extracted and panels moved; final view-layer cleanup (Phase F) outstanding.**

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

## Phase F: View-Layer Cleanup (OUTSTANDING)

Audit found stale pure-logic methods and ad-hoc dialogs still in the view layer.

### F.1 Shared dialog helper
- [ ] Create `app/view/shared/dialogs.py` (`show_error`/`show_info` reusing root via `parent=`).

### F.2 `pick_files_panel.py` (reference cleanup)

| Method | Lines | Category | Action |
|--------|-------|----------|--------|
| `parse_metadata_file` | 275-387 | Pure logic, duplicated in `FileDiscoveryService` | **Delete** (only service tests reference it) |
| `handle_metadata_parsing` | 421-462 | Dead adapter (no external callers) | **Delete** |
| `show_error_box` | 390-413 | UI, spawns new `tk.Tk()` | **Remove**, route to `dialogs.show_error` |
| `show_info_box` | 415-419 | UI, spawns new `tk.Tk()` | **Remove**, route to `dialogs.show_info` |
| `_collect_oct_files`, `_build_entries_for_file` | — | Correct thin delegators | Keep |
| `globalPicker`, `globalPickerThread`, progress popups, `breakAll` | — | UI-only | Keep |

- [ ] Delete `parse_metadata_file` and `handle_metadata_parsing` (verify no callers first).
- [ ] Replace dialog calls (lines 133, 167, 259) with `dialogs.show_error/show_info(self.root, ...)`.
- [ ] Run `pytest tests/unit/logic/test_rexview_file_discovery.py` + GUI smoke test.

### F.3 Audit remaining panels (per-panel checklist in REFACTOR-PLAN.md)
- [ ] `execution_panel.py`
- [ ] `image_panel.py`
- [ ] `global_settings_panel.py`
- [ ] `custom_settings_panel.py`
- [ ] `tree_view_panel.py`
- [ ] `instruction_panel.py` (expected: no logic)

### F.4 Enforce the boundary
- [ ] Add import-safety test: `app/logic/rexview/*` imports with no tkinter display.
- [ ] (Optional) test asserting `app/logic/**` contains no `import tkinter`.

---

## Completion Criteria

- [ ] Fully functional (manual GUI verification)
- [ ] 90%+ coverage on `app/logic/rexview/`
- [ ] Fully separated — **blocked by Phase F** (stale logic in `pick_files_panel.py`)
- [x] Standalone testable (`pytest tests/unit/logic/test_rexview_*.py` runs without tkinter)
- [ ] No ad-hoc dialogs (all via `app/view/shared/dialogs.py`)
