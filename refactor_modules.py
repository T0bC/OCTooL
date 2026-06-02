#!/usr/bin/env python3
"""Comprehensive refactor for OCTooL module renames.
Run from repo root:  python refactor_modules.py
"""
import os, re, shutil, sys
from pathlib import Path

# ============================================================
# CONFIG: add a dict here for every module you want to rename.
# ============================================================
MODULES = [
    {
        "active": False,
        "old_dir": "export_frames",
        "new_dir": "RexView",
        "old_file": "exportTab.py",
        "new_file": "rexViewTab.py",
        "old_import": "exportTab",
        "new_import": "rexViewTab",
        "old_display": "Export",
        "new_display": "RexView",
        "old_style": "Export",
        "new_style": "RexView",
        "old_enable": "ENABLE_EXPORT",
        "new_enable": "ENABLE_REXVIEW",
        "old_frame": "exportTabFrame",
        "new_frame": "rexViewTabFrame",
        "old_instruction": "export_getting_started",
        "new_instruction": "rexview_getting_started",
    },
    {
        "active": True,
        "old_dir": "analyze_frames",
        "new_dir": "AnnoLyze",
        "old_file": "analyzingTab.py",
        "new_file": "annoLyzeTab.py",
        "old_import": "analyzingTab",
        "new_import": "annoLyzeTab",
        "old_display": "Analyze",
        "new_display": "AnnoLyze",
        "old_style": "Analyze",
        "new_style": "AnnoLyze",
        "old_enable": "ENABLE_ANALYZE",
        "new_enable": "ENABLE_ANNOLYZE",
        "old_frame": "analyzingFrame",
        "new_frame": "annoLyzeFrame",
        "old_instruction": "analyze_getting_started",
        "new_instruction": "annolyze_getting_started",
    },
]

EXTS = (".py", ".spec", ".qmd", ".html", ".md", ".json")
CLEAN_PYCACHE = True


def clean_pycache(root):
    n = 0
    for p in root.rglob("__pycache__"):
        if p.is_dir():
            shutil.rmtree(p); n += 1
    return n


def rename_dirs(root, mods):
    for m in mods:
        if not m.get("active"): continue
        o, n = root / m["old_dir"], root / m["new_dir"]
        if not o.exists(): print(f"SKIP  dir: {o}"); continue
        if n.exists(): print(f"ERROR dir exists: {n}"); sys.exit(1)
        os.rename(o, n); print(f"RENAMED dir: {m['old_dir']} -> {m['new_dir']}")


def rename_files(root, mods):
    for m in mods:
        if not m.get("active"): continue
        o, n = root / m["old_file"], root / m["new_file"]
        if not o.exists(): print(f"SKIP  file: {o}"); continue
        if n.exists(): print(f"ERROR file exists: {n}"); sys.exit(1)
        os.rename(o, n); print(f"RENAMED file: {m['old_file']} -> {m['new_file']}")


def refactor(root, mods):
    script_path = Path(__file__).resolve()
    files = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and p.suffix in EXTS and p.resolve() != script_path]
    files.sort()
    for m in mods:
        if not m.get("active"): continue
        pairs = [
            (m["old_enable"], m["new_enable"]),
            (m["old_frame"], m["new_frame"]),
            (m["old_style"] + ".TButton", m["new_style"] + ".TButton"),
            (m["old_import"], m["new_import"]),
            (m["old_display"], m["new_display"]),
            (m["old_dir"], m["new_dir"]),
        ]
        if m.get("old_instruction"):
            pairs.append((m["old_instruction"], m["new_instruction"]))
        for old, new in pairs:
            if old == new: continue
            pat = re.compile(rf"\b{re.escape(old)}\b")
            for f in files:
                try:
                    txt = f.read_text(encoding="utf-8")
                except Exception:
                    continue
                new_txt, num = pat.subn(new, txt)
                if num:
                    f.write_text(new_txt, encoding="utf-8")
                    print(f"  {f.relative_to(root)}: {old!r} -> {new!r} ({num}x)")


if __name__ == "__main__":
    root = Path(__file__).parent.resolve()
    print(f"Root: {root}\n")
    rename_dirs(root, MODULES)
    rename_files(root, MODULES)
    refactor(root, MODULES)
    if CLEAN_PYCACHE:
        n = clean_pycache(root)
        print(f"\nCleaned {n} __pycache__ dirs")
    print("\nDone. Review with: git diff")
