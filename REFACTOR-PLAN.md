# OCTooL Refactor Plan (Canonical Reference)

This is the **stable, single source of truth** for how OCTooL is refactored to separate
GUI from business logic. It defines the *intent*, the *architecture pattern*, and the
*reusable process* every module must follow.

Per-module progress is tracked separately so this file rarely changes:

- `progress-rexview.md` — RexView (pilot module)
- `progress-carlquant.md` — CarlQuant
- `progress-annolyze.md` — AnnoLyze

---

## Intent

**Problem**: Panel classes instantiate tkinter widgets in `__init__` and read widget state
directly inside business-logic methods, which makes unit testing impossible without the
full GUI and entangles UI with computation.

**Goal**: Every module is split into:

- `app/logic/<module>/` — pure, tkinter-free business logic + Pydantic models (fully testable headlessly)
- `app/view/<module>/` — thin UI wrappers that gather widget state, call services, and render results

**Success looks like**:

- `pytest tests/unit/` runs with no tkinter display
- `app/logic/**` imports without importing tkinter
- Behavior is identical before/after refactor
- New features can be developed test-first

---

## Target Directory Structure

```
OCTooL/
├── app/
│   ├── logic/
│   │   ├── shared/                    # oct_functions, shared models
│   │   ├── rexview/                   # *_service.py + models.py
│   │   ├── carlquant/
│   │   └── annolyze/
│   └── view/
│       ├── shared/
│       │   ├── app_context.py         # UI coordination hub
│       │   ├── base_canvas_panel.py
│       │   ├── dialogs.py             # Centralized message boxes (reuse root)
│       │   └── widgets/               # Reusable UI components
│       ├── rexview/                   # thin panels
│       ├── carlquant/
│       └── annolyze/
└── tests/
    ├── unit/logic/                    # service + model tests (no tkinter)
    └── integration/                   # full-pipeline tests
```

---

## Canonical Architecture Pattern: Service + Collector

The **single pattern** every module follows.

### Layer Responsibilities

| Layer | Location | tkinter? | Responsibility |
|-------|----------|----------|----------------|
| **View (Panel)** | `app/view/<module>/*.py` | Yes | Build widgets, bind events, gather widget state, render results, show dialogs |
| **Model** | `app/logic/<module>/models.py` | No | Pydantic data structures passed across the boundary |
| **Service** | `app/logic/<module>/*_service.py` | No | Pure logic: calculations, file/zip/XML I/O, validation. Stateless where possible |
| **Shared UI** | `app/view/shared/dialogs.py` | Yes | Reusable message boxes that reuse the existing root, never spawn a new `tk.Tk()` |

### The Three Rules

1. **No logic in the view.** A panel method either (a) builds/binds widgets, (b) collects
   widget state into a model, (c) calls a service, or (d) renders a result. Nothing else.
2. **No tkinter in the logic.** `python -c "import app.logic.<module>.<service>"` must
   succeed headlessly.
3. **Models cross the boundary, not primitives.** Services accept/return Pydantic models,
   not loose tuples or widget references.

### AppContext Key Namespacing

Panels and frames are registered in a single shared `AppContext` (`panels`/`frames` dicts).
Because all modules share it, **keys must be module-prefixed to avoid collisions**:

- RexView → `rex_*` (e.g. `rex_image`)
- AnnoLyze → `anno_*` (e.g. `anno_image`)
- CarlQuant → `carl_*` (e.g. `carl_image`)

A bare key like `"image"` registered by two modules silently overwrites whichever loaded
first, causing `get_panel()` to return the wrong panel at runtime (this caused the RexView
`Show` button to call an AnnoLyze panel). When refactoring a module, give every
`register_panel`/`register_frame`/`get_panel`/`get_frame` key the module prefix.

### Method Categorization (do this first for every panel)

Label each panel method:

- **UI-only** → keep in the panel (widget creation, `.grid()`, event binding, canvas draw).
- **Pure logic** → must live in a service. If a copy still lives in the panel,
  **delete the panel copy** and call the service.
- **Mixed** → split into a `_collect_*()` collector (stays in panel) + a service call.

### Collector Pattern

```python
# In the panel (view layer) — knows about widgets:
def _collect_<feature>_config(self) -> <Feature>Config:
    return <Feature>Config.from_gui_state(
        field1=self.widget1.get(),
        field2=self.widget2.instate(["selected"]),
    )
```

```python
# In models.py (logic layer) — no tkinter:
class <Feature>Config(BaseModel):
    field1: str
    field2: bool

    @classmethod
    def from_gui_state(cls, *, field1, field2) -> "<Feature>Config":
        return cls(field1=field1, field2=bool(field2))
```

### Wiring Pattern

```python
# Before (logic mixed into view):
def some_action(self):
    value = self.widget.get()
    result = complex_calculation(value)
    self.other_widget.set(result)

# After (view delegates to service):
def some_action(self):
    config = self._collect_config()
    result = self.service.calculate(config)   # pure logic
    self.other_widget.set(result.display_value)
```

### Error Handling & Robustness

The app must **never fail silently** — especially in windowed PyInstaller builds where
stderr is invisible. Two layers work together:

1. **Global safety net (required, once at startup).** `install_tk_exception_handler(root)`
   from `utils/error_handler.py` overrides the root window's `report_callback_exception`.
   Tkinter routes *every* uncaught callback exception (button commands, event bindings,
   lambdas, `after` jobs) through this, so all UI errors get a popup + log even when the
   callback is an undecorated lambda. Installed in `MainGui.__init__` right after the root
   `tk.Tk()` is created.
2. **Targeted decorator (optional, for context).** `@handle_errors("<where>")` on a method
   adds a clearer custom message and function-level args/kwargs to the log. Use it on
   important entry-point methods; it is *not* a substitute for the global net.

Rules for refactored panels:

- **Do not** create per-panel `tk.Tk()` instances or ad-hoc try/except-to-stderr blocks.
- View-layer user messaging goes through `app/view/shared/dialogs.py`.
- Logic-layer services **raise** typed exceptions (e.g. `ValueError`) or return
  result/error tuples; they never show dialogs. The view decides how to surface them.
- A lambda wired to `command=`/`bind` is covered by the global net, but prefer a named
  method when it does real work so it can be tested and optionally decorated.

### Centralized Dialogs

All user messaging goes through `app/view/shared/dialogs.py`, reusing the app root
(`context.root`) instead of throwaway `tk.Tk()` instances:

```python
# app/view/shared/dialogs.py
from tkinter import messagebox

def show_error(parent, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=parent)

def show_info(parent, title: str, message: str) -> None:
    messagebox.showinfo(title, message, parent=parent)
```

Panels call `dialogs.show_error(self.root, title, msg)` instead of defining their own
`show_error_box`/`show_info_box` helpers.

---

## Reusable Per-Panel Refactor Checklist

Copy this into a module progress file for each panel:

- [ ] Categorize every method (UI-only / pure logic / mixed).
- [ ] Confirm the corresponding service + models exist in `app/logic/<module>/`.
- [ ] **Delete** any pure-logic method duplicated from the service (verify no callers first).
- [ ] Add `_collect_*()` collectors for mixed methods.
- [ ] Replace inline logic with service calls.
- [ ] Replace ad-hoc dialogs with `app/view/shared/dialogs.py`.
- [ ] Verify `app/logic/<module>` imports without tkinter.
- [ ] Run module tests; add tests for any newly-extracted logic.

---

## Reusable Per-Module Process

1. **Analyze panels** — list methods, categorize (UI-only / logic / mixed), identify data
   flowing between them (→ becomes a Pydantic model).
2. **Models first** — define `<Feature>Config` / `<Feature>Params` / `<Feature>Result` in
   `app/logic/<module>/models.py`.
3. **Service with pure logic** — `app/logic/<module>/<feature>_service.py`, no tkinter.
4. **Unit tests** — `tests/unit/logic/test_<module>_<feature>.py`, GIVEN-WHEN-THEN.
5. **Collectors** — add `_collect_*()` to panels.
6. **Wire** — replace inline logic with service delegation, one method at a time.
7. **Integration tests** — `tests/integration/test_<module>_pipeline.py`.
8. **Move UI files** — relocate panels to `app/view/<module>/`, update imports, run all tests.

---

## Testing Guidelines

1. **GIVEN-WHEN-THEN** structure for all tests.
2. **Test behavior, not implementation** — don't mock internal methods.
3. **One behavior per test**.
4. **Test pyramid**: ~50% unit, ~30% integration, ~20% e2e.
5. **Mock only external resources** (file I/O, network) — not internal classes.
6. **Pydantic for validation** — models validate at construction time.

---

## Key Lessons (from RexView pilot)

1. **Start with the most complex panel** — it establishes the patterns.
2. **Models before services** — data structures clarify the service interface.
3. **Incremental wiring** — replace one method at a time, test after each change.
4. **Keep collectors in the UI layer** — they know about widgets.
5. **Service methods take models, not primitives**.
6. **Progress callbacks for long operations** — service accepts a `Callable` for UI updates.
7. **Factory methods on models** — `Config.from_gui_state()` handles widget→Python conversion.
8. **"Move complete" ≠ "clean"** — after relocating files, explicitly delete leftover
   duplicate logic and ad-hoc dialogs (this was missed in RexView Phase E, see Phase F).
