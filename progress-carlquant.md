# CarlQuant Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **Milestone 4 (view relocation) COMPLETE — refactor essentially done.**
Logic lives in `app/logic/carlquant/` (tkinter-free, import-safety enforced); all view
code lives in `app/view/carlquant/`; the old `CarlQuant/` folder is removed. The main
analysis flow is split (pure compute in `AnalysisService`, UI/threading in
`analysis_runner.py`). Full suite **444 passing**; `carlQuantTab` imports verified.
Remaining: optional integration test + manual GUI smoke test.

---

## Starting Notes

- `CarlQuant/carl_quant_core.py` and `CarlQuant/interpolation.py` already contain pure
  functions (surface detection, region extraction, math) — good extraction candidates.
- `CarlQuant/specimen_model.py` (dataclasses) and `CarlQuant/data_io.py` (Excel/JSON/PIL
  I/O) are already tkinter-free.
- `carl_quant_core.py` was tkinter-tainted only via `progress_dialog` + `utils.error_handler`,
  both used solely inside `run_carl_quant`. Those imports are now **lazy** (inside
  `run_carl_quant`), so the module imports headlessly and its pure compute functions are
  reusable by the logic layer.

## Milestone 1 — Logic foundation (DONE)

Logic package `app/logic/carlquant/` (tkinter-free, verified by import-safety test):

| File | Contents | Status |
|------|----------|--------|
| `models.py` | Surfaces the pure boundary models (`RegionConfig`, `AirConfig`, `SpecimenConfig`, `RegionStats`, `Surface`, `LesionDepth`, `SliceResult`, `Specimen`) + `DepthDetectionMethod` from the canonical `CarlQuant.specimen_model` / core | Done |
| `analysis_service.py` | `AnalysisService` (`detect_surface`, `extract_regions`, `calculate_lesion_depth` delegators) + the extracted pure per-slice pipeline `analyze_slice` / `analyze_image` / `analyze_slices` (progress-callback + cancellation, **no tkinter**) and `SliceAnalysis` result | Done |
| `interpolation_service.py` | `InterpolationService` wrapping the keyframe engine (regions/AIR) | Done |
| `data_service.py` | Surfaces `DataLoader` / `DataSaver` + helpers | Done |
| `__init__.py` | Package exports | Done |

### Tests (34 passing, 100% coverage; full suite green)

- [x] `test_carlquant_models.py` — RegionConfig buffers, SpecimenConfig, enum
- [x] `test_carlquant_interpolation.py` — single/multi keyframe, backfill, forward-fill,
      generic descriptor, AIR
- [x] `test_carlquant_analysis.py` — surface detection, no-region placeholder path, image
      loading, sequential iteration, progress callback, cancellation, region-config path,
      extract_regions/calculate_lesion_depth delegators
- [x] `test_carlquant_import_safety.py` — no tkinter in `app/logic/carlquant/`

Run (coverage): `& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/ --cov=app.logic.carlquant --cov-report=term-missing`

## Milestone 2 — Analysis pipeline logic/view split (DONE)

- [x] `AnalysisService.analyze_specimen(...)` — pure, tkinter-free per-specimen pipeline
      (parallel via `ProcessPoolExecutor`/`process_slice_parallel` + sequential), result
      storage via `DataSaver`, optional persistence, status setting. UI is injected via
      `on_status` / `on_slice_done` / `on_mode` / `on_error` / `is_cancelled` callbacks.
      Returns `SpecimenAnalysisResult` (status: Completed/Partial/Cancelled).
- [x] `app/view/carlquant/analysis_runner.py` — `run_carl_quant(context)` thin UI/threading
      wrapper: builds `ProgressDialog`, runs the worker thread, maps service callbacks to
      dialog updates, updates the specimen table + status bar, handles skip choice and
      error popups. The pure compute is fully delegated to the service.
- [x] `CarlQuant/load_images_panel.py` rewired to import `run_carl_quant` from
      `app.view.carlquant.analysis_runner`.
- [x] `run_carl_quant` removed from `CarlQuant/carl_quant_core.py` (now pure compute +
      `process_slice_parallel` only).
- [x] Tests: `test_carlquant_specimen.py` (sequential, region-config path, result_lock,
      save-to-disk, parallel, cancellation, status callbacks). Full suite **439 passing**;
      `app/logic/carlquant` at **92%** (uncovered = parallel-cancellation timing branches).

## Milestone 3 — Logic relocation (DONE)

- [x] `git mv` the pure logic into `app/logic/carlquant/`: `specimen_model.py`,
      `annotation_colors.py`, `interpolation.py`, `data_io.py`, `carl_quant_core.py`.
- [x] Rewired internal imports of the moved files + the service wrappers (`models.py`,
      `analysis_service.py`, `interpolation_service.py`, `data_service.py`) to
      `app.logic.carlquant.*` (no more `CarlQuant.*` logic imports).
- [x] Updated all consumers to import logic from `app.logic.carlquant` (public API) or
      `app.logic.carlquant.<module>`: `settings_panel`, `results_panel`,
      `load_images_panel`, `image_viewer_panel`, `specimen_panel`, `ascan_viewer`,
      `annotation_renderer`.
- [x] Import-safety test now scans the relocated modules and still passes (logic
      tkinter-free). Full suite **444 passing**; all edited panels `py_compile` clean;
      `app.view.carlquant.analysis_runner` + `app.logic.carlquant` import-chain verified.

> Note: `app/logic/carlquant` line-coverage now reads lower (~68%) only because the large
> legacy modules (`carl_quant_core` 564 stmts, `data_io` 386) are counted in the package;
> the newly-written service/model code stays fully covered. Backfilling tests for the
> legacy compute/I/O is optional follow-up.

## Milestone 4 — View relocation (DONE)

- [x] `git mv` all 8 view files to `app/view/carlquant/`: `settings_panel.py`,
      `specimen_panel.py`, `results_panel.py`, `image_viewer_panel.py`,
      `load_images_panel.py`, `progress_dialog.py`, `annotation_renderer.py`,
      `ascan_viewer.py`.
- [x] Updated cross-imports to `app.view.carlquant.*`: `results_panel`→`ascan_viewer`,
      `image_viewer_panel`→`annotation_renderer`, `analysis_runner`→`progress_dialog`.
- [x] Updated `carlQuantTab.py` panel imports to `app.view.carlquant.*`.
- [x] Removed the now-empty `CarlQuant/` folder.
- [x] Routed `load_images_panel`'s validation error dialog through
      `app/view/shared/dialogs.py` (`show_error`, anchored to the app root).
- [x] Verified: full view import chain (`carlQuantTab`, panels, runner) imports
      headlessly; full suite **444 passing**; touched files `py_compile` clean.

## Optional follow-up

- [ ] Integration test: `tests/integration/test_carlquant_analysis.py`.
- [ ] Backfill unit tests for legacy compute/I/O (`carl_quant_core`, `data_io`) to raise
      `app/logic/carlquant` line-coverage.
- [ ] Manual GUI smoke test (load → set regions → analyze → cancel/complete → view results).
