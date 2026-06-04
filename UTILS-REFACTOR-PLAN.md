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

### Step D — Move tkinter infra into `app/view/shared`
- [ ] Move `error_handler.py` popup/`install_tk_exception_handler`/`handle_errors` into
      `app/view/shared/error_handler.py` (importing `log_error_to_file` from logic.shared).
- [ ] Move `AppContext` into `app/view/shared/app_context.py`.
- [ ] Leave shims at `utils/error_handler.py` and `utils/app_context.py`.
- [ ] Verify app still launches.

### Step E — Move the shared view widgets
For each of `tool_tip.py`, `status_bar.py`, `instruction_renderer.py`, `metadata_prompt.py`,
`about_dialog.py`, `help_dialog.py` and `base/base_canvas_panel.py`:
- [ ] Move file to `app/view/shared/`.
- [ ] Update its internal imports to the new logic/view shared paths.
- [ ] Leave a re-export shim at the old path (`utils/<file>.py`, `base/__init__.py`).
- [ ] Verify app launches after each move.

### Step F — Relocate assets and update references (D4)
- [ ] Move `utils/instructions.json` → `assets/instructions.json`.
- [ ] Move `utils/fonts/` → `assets/fonts/`.
- [ ] Update `resource_path` call sites:
      `"utils/instructions.json"` → `"assets/instructions.json"`,
      `"utils/fonts/LSANS.TTF"` → `"assets/fonts/LSANS.TTF"`
      (in `instruction_renderer.py`, `help_dialog.py`, `oct_functions.py`).
- [ ] Update `OCTooL.spec` `datas`: `('assets/fonts', 'assets/fonts')`,
      `('assets/instructions.json', 'assets')`.
- [ ] Verify a windowed PyInstaller build still finds fonts + instructions.

### Step G — Relocate the dev script (D4)
- [ ] Move `png_to_ico_script.py` → `scripts/png_to_ico_script.py`.
- [ ] Confirm it is not imported anywhere (it is standalone).

### Step H — Migrate all callers off the shims
- [ ] Find every remaining `from utils...`, `from base...`, and `import utils...`.
- [ ] Repoint each to its `app.logic.shared.*` / `app.view.shared.*` home.
- [ ] Update `tests/` imports (e.g. `from utils import oct_functions` → new path).
- [ ] Run full `pytest`.

### Step I — Move root tab files into their module view folders (D2)
- [ ] Move `rexViewTab.py` → `app/view/rexview/rexViewTab.py`.
- [ ] Move `annoLyzeTab.py` → `app/view/annolyze/annoLyzeTab.py`.
- [ ] Move `carlQuantTab.py` → `app/view/carlquant/carlQuantTab.py`.
- [ ] Update each tab's internal imports.
- [ ] Leave a root shim for each only if still referenced; otherwise update callers directly.

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
