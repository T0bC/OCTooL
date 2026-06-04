# Export Parallelization Plan (RexView)

Goal: speed up OCT export by parallelizing the currently-sequential per-file
pipeline, plus a low-risk quick win. Implementation is TDD (Red -> Green ->
Refactor) at each step.

## Context / Findings

- Each queued file flows through `ExportService.run_export`
  (`app/logic/rexview/export_service.py`), driven sequentially by the queue
  loop in `app/view/rexview/execution_panel.py` (`mainRoutines`).
- The current `ThreadPoolExecutor(max_workers=1)` there only keeps the UI
  responsive; it provides **no real parallelism**.
- Cost profile by data type:
  - **Processed** path (`oct_functions.createImageFromRaw`, processed branch):
    pure vectorized numpy, fast, memory-bound.
  - **Raw-spectral** path: the real cost. Per slice it runs a large FFT matrix
    multiply (`nftm @ ...`), `np.percentile` + `np.convolve` noise floor, and a
    `median_filter` in `octToGV`. Heavily **CPU-bound** and the dominant cost.
- Culprits:
  1. `gc.collect()` on **every slice** in `run_export` — expensive, near-useless.
  2. No real parallelism (files are independent and CPU-bound).
  3. Redundant `metadata.to_xml_dict()` rebuilds per slice.

## Why multiprocessing (not threads)

- File-level multiprocessing is low overhead here: workers receive only small
  picklable args (`file_path`, `params`, `config`), open their own archive, and
  write images straight to disk. No large numpy arrays cross process boundaries.
- Per-file work is seconds; process spawn (~100-300 ms on Windows `spawn`) and
  pickling are negligible in comparison.
- Threads only partially help (numpy/scipy release the GIL, Python glue does
  not), so **processes** are the right tool for the raw-spectral path.

Risks accounted for:
- Windows `spawn`: worker must be a top-level, picklable function.
- No tkinter in workers: marshal all UI updates back to the main thread.
- Memory blow-up: cap workers (memory-aware; fewer for raw-spectral data).
- Cancellation: cooperative cancel in the coordinator.

## Steps

### Step 1 - Quick win (gc + dict hoist)
- Tests (Red):
  - `test_run_export_does_not_gc_per_slice`: patch `gc.collect`, assert at most
    once per file.
  - `test_run_export_builds_xml_dict_once`: spy on `metadata.to_xml_dict`,
    assert minimal calls.
- Impl (Green):
  - Remove per-slice `gc.collect()` in `run_export`.
  - Compute `xml_dict = metadata.to_xml_dict()` once; pass down to
    `process_slice` / `export_video_image`.

### Step 2 - Picklable worker function
- Tests (Red):
  - `test_export_one_file_returns_result`.
  - `test_export_one_file_is_picklable` (`pickle.dumps(export_one_file)`).
- Impl (Green):
  - New module `app/logic/rexview/export_worker.py` with a **top-level**
    `export_one_file(file_path, params, config)` that builds its own
    `ExportService`, runs the export, and returns an `ExportResult`. No tkinter,
    no closures.

### Step 3 - Structured `ExportResult`
- Tests (Red):
  - `test_export_result_fields`: `file_path`, `exported_files`, `failed_count`,
    `error`.
  - `test_run_export_returns_result`: adapt existing tests; keep
    `.exported_files` accessor for backward compat.
- Impl (Green):
  - Add `ExportResult` to `app/logic/rexview/models.py`. `run_export` returns it.
    Workers return plain picklable data (paths as `str`).

### Step 4 - `ParallelExportCoordinator`
- Tests (Red):
  - `test_coordinator_caps_workers`: `min(cpu-1, queue_len, max_cap)`.
  - `test_coordinator_runs_all_files` (with `export_one_file` patched).
  - `test_coordinator_cancellation`: no new tasks after `cancel()`.
  - `test_coordinator_handles_worker_exception`: failing file -> `ExportResult`
    with error, pool survives.
- Impl (Green):
  - New `app/logic/rexview/parallel_export.py` with `ParallelExportCoordinator`
    wrapping `concurrent.futures.ProcessPoolExecutor`, yielding via
    `as_completed`. Memory-aware worker cap. Pure logic, unit-testable with the
    pool patched.

### Step 5 - Wire `execution_panel` (UI-safe)
- Tests (Red):
  - `test_coordinator_progress_queue`: results pushed to a `queue.Queue` for the
    UI to drain.
- Impl (Green):
  - Replace the sequential loop in `mainRoutines` with: submit all rows to the
    coordinator from the background thread, drain completed `ExportResult`s, and
    update TreeView via `root.after(...)` (tkinter only on UI thread).
  - Keep a single-worker fallback (workers=1).
  - `breakAll()` calls `coordinator.cancel()`.

### Step 6 - Worker-count config
- Tests (Red):
  - `test_export_config_worker_count_default`.
  - `test_worker_count_respects_user_override`.
- Impl (Green):
  - Add `worker_count` (optional) to `ExportConfig` with memory-aware default;
    UI control later.

### Step 7 - Verification & docs
- Run `pytest -m unit` and `tests/integration/test_export_pipeline.py` against
  real `.oct` files (raw-spectral path is `# pragma: no cover` in unit tests, so
  integration is essential).
- Benchmark sequential vs parallel on a representative folder.
- Add a change-log entry under Version 2026.3 Performance section.

## Test locations
- `tests/unit/logic/test_rexview_export.py`
- `tests/unit/logic/test_rexview_parallel_export.py` (new)
- `tests/integration/test_export_pipeline.py`
