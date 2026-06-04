# OCTooL `utils/` + Root-Files Refactor Plan

Companion to `REFACTOR-PLAN.md`. That document defined the `app/logic` + `app/view`
split per module. This document defines how to fold the remaining **`utils/` package**,
the **`base/` package**, the **root tab files**, and **loose assets/scripts** into the
`app/` structure so that only the entry point (`OCTooL.py`) and project metadata remain at
the repository root.

---

## Confirmed Decisions

These were agreed before writing the plan and constrain every step below:

- **D1 — No `app/core/`.** Cross-cutting helpers are split between `app/logic/shared/`
  (pure, tkinter-free) and `app/view/shared/` (tkinter-dependent).
- **D2 — Move tabs, keep filenames.** `rexViewTab.py`, `annoLyzeTab.py`, `carlQuantTab.py`
  move into their `app/view/<module>/` folders; `MainGui.py` moves into `app/view/`. Existing
  filenames are preserved (no snake_case rename in this pass).
- **D3 — Shim-first, then cleanup.** Each physical move leaves a thin re-export shim at the
  old import path so the app keeps running. Callers are migrated incrementally. A final step
  deletes all shims.
- **D4 — Relocate assets & scripts.** `instructions.json` + `fonts/` move to a top-level
  `assets/`; `png_to_ico_script.py` moves to a top-level `scripts/`. `OCTooL.spec` and
  `resource_path` callers are updated.

---

## Guiding Principle (the "Python way" for this codebase)

For an actively maintained scientific tool, the idiomatic target is:

- **One installable package (`app/`)** containing all application code, with a clear
  `logic` (pure/testable) vs `view` (tkinter) boundary already established.
- **A thin entry point at the root** (`OCTooL.py`) that only bootstraps multiprocessing and
  launches the GUI.
- **Assets and dev scripts kept out of the import path** (`assets/`, `scripts/`) so they are
  never accidentally imported and are bundled explicitly by PyInstaller.
- **No top-level helper grab-bag** (`utils/`): cross-cutting code is classified by whether it
  touches tkinter, honoring the existing "no tkinter in logic" rule.

---

## Target End-State Layout

```
OCTooL/
├── OCTooL.py                      # ONLY remaining root Python module (entry point)
├── OCTooL.spec
├── pyproject.toml / requirements.txt / README.md / LICENSE / CITATION.cff
├── assets/
│   ├── instructions.json
│   └── fonts/LSANS.TTF
├── scripts/
│   └── png_to_ico_script.py
├── logs/                          # runtime output (gitignored)
├── app/
│   ├── view/
│   │   ├── MainGui.py
│   │   ├── shared/
│   │   │   ├── app_context.py        # AppContext (UI coordination hub)
│   │   │   ├── base_canvas_panel.py  # moved from base/
│   │   │   ├── error_handler.py      # popups + install_tk_exception_handler + handle_errors
│   │   │   ├── dialogs.py            # (already here)
│   │   │   ├── tool_tip.py
│   │   │   ├── status_bar.py
│   │   │   ├── instruction_renderer.py
│   │   │   ├── metadata_prompt.py
│   │   │   ├── about_dialog.py
│   │   │   └── help_dialog.py
│   │   ├── rexview/   (+ rexViewTab.py)
│   │   ├── annolyze/  (+ annoLyzeTab.py)
│   │   └── carlquant/ (+ carlQuantTab.py)
│   └── logic/
│       ├── shared/
│       │   ├── oct_functions.py      # REAL implementation (no longer a shim)
│       │   ├── paths.py              # resource_path (pure)
│       │   ├── logging_utils.py      # log_error_to_file (pure file I/O)
│       │   └── models.py
│       ├── rexview/ ...
│       ├── carlquant/ ...
│       └── annolyze/ ...
└── tests/
```

---

## Classification of Current `utils/` + `base/`

| File | Touches tkinter? | Destination |
|------|------------------|-------------|
| `oct_functions.py` | No (after decorator removal) | `app/logic/shared/oct_functions.py` |
| `app_context.py` → `resource_path` | No | `app/logic/shared/paths.py` |
| `app_context.py` → `AppContext` | No (but UI coordination) | `app/view/shared/app_context.py` |
| `error_handler.py` → `log_error_to_file` | No | `app/logic/shared/logging_utils.py` |
| `error_handler.py` → popups / `install_tk_exception_handler` / `handle_errors` | Yes | `app/view/shared/error_handler.py` |
| `tool_tip.py` | Yes | `app/view/shared/tool_tip.py` |
| `status_bar.py` | Yes | `app/view/shared/status_bar.py` |
| `instruction_renderer.py` | Yes | `app/view/shared/instruction_renderer.py` |
| `metadata_prompt.py` | Yes | `app/view/shared/metadata_prompt.py` |
| `about_dialog.py` | Yes | `app/view/shared/about_dialog.py` |
| `help_dialog.py` | Yes | `app/view/shared/help_dialog.py` |
| `base/base_canvas_panel.py` | Yes | `app/view/shared/base_canvas_panel.py` |
| `instructions.json`, `fonts/` | n/a (assets) | `assets/` |
| `png_to_ico_script.py` | n/a (dev tool) | `scripts/` |
| `logs/` | n/a (runtime) | top-level `logs/` (gitignored) |

> **Known coupling to resolve (Step C):** `oct_functions.py` currently imports
> `handle_errors` (tkinter) and `resource_path`. To keep `app/logic/shared` tkinter-free,
> the `@handle_errors` decorator must be removed from logic functions (services/views handle
> errors per `REFACTOR-PLAN.md`), and `resource_path` must come from the new pure
> `app/logic/shared/paths.py`.

> **`resource_path` depth fix (Step B — DONE):** the old implementation derived the project
> root via `dirname(dirname(abspath(__file__)))` (2 levels, valid from `utils/`). In its new
> home `app/logic/shared/paths.py` (3 packages deep) the project root is **4** `dirname` calls
> up (`paths.py` -> `shared` -> `logic` -> `app` -> root). Implemented with 4 nested
> `os.path.dirname` calls. Verified in dev: `resource_path('icons/thumb_4.ico')` resolves to
> the project root. PyInstaller (`sys._MEIPASS`) branch unchanged and still to be verified in a
> bundled build.

---

## Incremental Steps

Each step is independently shippable and ends green (`pytest` + app launches). Steps A–E are
prerequisites that unblock the rest; F–J are the moves; K is cleanup.

### Step A — Scaffold the new homes (no behavior change) — DONE
- [x] Create `assets/` and `scripts/` directories (each with a `.gitkeep`).
- [x] Confirm `app/view/shared/__init__.py` and `app/logic/shared/__init__.py` exist (both present).
- [x] No imports change yet. Pure scaffolding.

### Step B — Extract pure helpers into `app/logic/shared` — DONE
- [x] Create `app/logic/shared/paths.py` with `resource_path` (dirname depth fixed: 4 levels up).
- [x] Create `app/logic/shared/logging_utils.py` with `log_error_to_file` (writes to project-root `logs/`).
- [x] In `utils/app_context.py` and `utils/error_handler.py`, **re-export** from the new
      modules (shim direction: old path → new module) so existing imports still work.
- [x] Point the `logs/` directory at the project root, not the module dir (added `logs/` to `.gitignore`).
- [x] Verify: `python -c "import app.logic.shared.paths, app.logic.shared.logging_utils"` (passed; full `pytest` = 444 passed).

### Step C — Make `app/logic/shared/oct_functions.py` the real implementation — DONE
- [x] Moved the full body of `utils/oct_functions.py` into `app/logic/shared/oct_functions.py`,
      replacing the previous re-export shim.
- [x] Removed `@handle_errors` decorators from these functions (logic stays tkinter-free);
      callers/services now surface errors.
- [x] Switched its `resource_path` import to `app.logic.shared.paths`.
- [x] Replaced `utils/oct_functions.py` with a thin shim re-exporting from the new location.
- [x] Verified: `import app.logic.shared.oct_functions` succeeds with **no tkinter** in `sys.modules`.
- [x] Updated `tests/unit/logic/test_oct_functions.py` import to `from app.logic.shared import oct_functions`.
      Full `pytest` = 444 passed.
- [ ] **Deferred to Step F:** the font path is still `resource_path("utils/fonts/LSANS.TTF")`;
      it moves to `assets/fonts/LSANS.TTF` during the asset relocation step.

### Step D — Move tkinter infra into `app/view/shared` — DONE
- [x] Moved `show_error_popup`/`install_tk_exception_handler`/`handle_errors` into
      `app/view/shared/error_handler.py` (imports `log_error_to_file` from `app.logic.shared.logging_utils`).
- [x] Moved `AppContext` into `app/view/shared/app_context.py`.
- [x] Left thin re-export shims at `utils/error_handler.py` and `utils/app_context.py`
      (`utils/app_context.py` also re-exports `resource_path`).
- [x] Verified: shim + new-path imports succeed, all GUI modules `py_compile` clean,
      full `pytest` = 444 passed.

### Step E — Move the shared view widgets — DONE
For each of `tool_tip.py`, `status_bar.py`, `instruction_renderer.py`, `metadata_prompt.py`,
`about_dialog.py`, `help_dialog.py` and `base/base_canvas_panel.py`:
- [x] Moved each file to `app/view/shared/`.
- [x] Updated internal imports to the new shared homes:
      `instruction_renderer.py` → `resource_path` from `app.logic.shared.paths`;
      `help_dialog.py`/`about_dialog.py` → `handle_errors` from `app.view.shared.error_handler`,
      `resource_path` from `app.logic.shared.paths`;
      `base_canvas_panel.py` → `Tooltip`/`handle_errors`/`InstructionRenderer` from `app.view.shared.*`,
      `resource_path` from `app.logic.shared.paths`.
      (`tool_tip.py`, `status_bar.py`, `metadata_prompt.py` had no internal `utils`/`base` imports.)
- [x] Left re-export shims at the old paths (`utils/<file>.py`, and `base/__init__.py` for `BaseCanvasPanel`).
- [x] Verified: shim + new-path imports succeed, GUI modules `py_compile` clean, full `pytest` = 444 passed.
      Asset paths inside `instruction_renderer.py` (`utils/instructions.json`) and `base_canvas_panel.py`
      remain unchanged — they move in Step F.

### Step F — Relocate assets and update references (D4) — DONE
- [x] Moved `utils/instructions.json` → `assets/instructions.json`.
- [x] Moved `utils/fonts/` → `assets/fonts/`.
- [x] Updated `resource_path` call sites:
      `"utils/instructions.json"` → `"assets/instructions.json"`,
      `"utils/fonts/LSANS.TTF"` → `"assets/fonts/LSANS.TTF"`
      (in `app/view/shared/instruction_renderer.py` default arg + `app/view/shared/help_dialog.py` +
      `app/logic/shared/oct_functions.py`).
- [x] Updated `OCTooL.spec` `datas`: `('assets/fonts', 'assets/fonts')`,
      `('assets/instructions.json', 'assets')`.
- [x] Verified in dev: `resource_path('assets/fonts/LSANS.TTF')` and `resource_path('assets/instructions.json')`
      both exist and the JSON loads; full `pytest` = 444 passed.
- [ ] **Still recommended:** run a windowed PyInstaller build to confirm the bundled app finds fonts +
      instructions (could not be exercised here).

### Step G — Relocate the dev script (D4) — DONE
- [x] Moved `png_to_ico_script.py` → `scripts/png_to_ico_script.py`.
- [x] Confirmed it is not imported anywhere (grep for `png_to_ico_script` = no results; standalone).

### Step H — Migrate all callers off the shims — DONE
- [x] Found and repointed every `from utils...` / `from base...` import across 28 files
      (tabs, `MainGui.py`, `OCTooL.py`, and all `app/view/*` + `app/logic/rexview/*` modules)
      to their `app.logic.shared.*` / `app.view.shared.*` homes:
      `app_context.AppContext` → `app.view.shared.app_context`;
      `app_context.resource_path` → `app.logic.shared.paths`;
      `status_bar`/`error_handler`/`tool_tip`/`instruction_renderer`/`metadata_prompt`/
      `help_dialog`/`about_dialog` → `app.view.shared.*`;
      `oct_functions` → `app.logic.shared`; `base.BaseCanvasPanel` → `app.view.shared.base_canvas_panel`.
- [x] `tests/` imports already pointed at new paths (only `test_oct_functions.py`, updated in Step C).
- [x] Verified: grep for `^from (utils|base)` / `^import (utils|base)` = no results; full `pytest` = 444 passed.

### Step I — Move root tab files into their module view folders (D2) — DONE
- [x] Moved `rexViewTab.py` → `app/view/rexview/rexViewTab.py`.
- [x] Moved `annoLyzeTab.py` → `app/view/annolyze/annoLyzeTab.py`.
- [x] Moved `carlQuantTab.py` → `app/view/carlquant/carlQuantTab.py`.
- [x] No internal import changes needed — the tabs already use absolute `app.view.*` imports.
- [x] No root shims: `MainGui.py` was the only referencer; updated its imports to
      `from app.view.<module> import <Tab>` (preserving `<Tab>.addContent` usage).
- [x] Verified: tabs + `MainGui.py` + `OCTooL.py` `py_compile` clean, tab modules import OK,
      full `pytest` = 444 passed.

### Step J — Move `MainGui.py` into `app/view` (D2)
- [ ] Move `MainGui.py` → `app/view/MainGui.py`.
- [ ] Update its imports of the tab modules to `app.view.<module>.<Tab>`.
- [ ] Update `OCTooL.py`: `import MainGui as mainGui` → `from app.view import MainGui as mainGui`
      and `from app.view.shared.error_handler import show_error_popup, log_error_to_file`
      (or split: `log_error_to_file` from logic.shared).
- [ ] Verify the app launches from `OCTooL.py`.

### Step K — Delete all shims and the empty packages
- [ ] Remove every re-export shim left in `utils/` and `base/`.
- [ ] Delete the now-empty `utils/` and `base/` directories.
- [ ] Grep the repo to confirm zero `from utils`, `import utils`, `from base`, `import base`.
- [ ] Confirm only `OCTooL.py` + project metadata remain at the root.
- [ ] Run full `pytest`, launch the app

---

## Verification Commands (run after each step)

Use the project conda interpreter for every Python/pytest invocation:

```pwsh
# logic stays tkinter-free
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -c "import app.logic.shared.oct_functions; import app.logic.shared.paths; import app.logic.shared.logging_utils"

# tests
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/unit -q
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/ -q

# with coverage (example)
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/ --cov=app.logic.annolyze --cov-report=term-missing

# app launches
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" OCTooL.py

# no stale imports (Step H/K gate)
# (use the IDE grep tool for: 'from utils', 'import utils', 'from base', 'import base')
```

---

## Risk Notes

- **`resource_path` depth** is the single most likely breakage (Step B/F). Test both dev run
  and a bundled build.
- **`handle_errors` removal from logic** (Step C) changes error surfacing for OCT functions;
  confirm the calling views/services still report failures to the user.
- **PyInstaller `datas`** must be updated in lockstep with the asset move (Step F), or the
  packaged app will silently fail to find fonts/instructions (invisible in windowed builds).
- **Shim lifetime**: shims exist only between the move step and Step K. Do not let them leak
  into new code — always import from the final `app.*` path.
```
