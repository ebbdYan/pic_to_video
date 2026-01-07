"""PyInstaller runtime hook to ensure Tk/Tcl resources are discoverable.

Some Windows builds of PyInstaller apps that use tkinter may fail at runtime with:
    ModuleNotFoundError: No module named 'tkinter'

This hook tries to make the bundled Tcl/Tk libraries discoverable by setting
TCL_LIBRARY / TK_LIBRARY and ensuring the corresponding directory is on PATH.

Notes:
- If the Python environment used to build the exe does not include Tk/Tcl at all,
  no hook can fix it. In that case install a full Python distribution that ships
  with Tcl/Tk and rebuild.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _set_env_if_missing(key: str, value: str) -> None:
    if value and not os.environ.get(key):
        os.environ[key] = value


def _add_to_path(dir_path: str) -> None:
    if not dir_path:
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if dir_path not in parts:
        os.environ["PATH"] = dir_path + os.pathsep + current


def _main() -> None:
    # When running as a PyInstaller onefile/onedir app, sys._MEIPASS points to
    # the extraction directory.
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return

    root = Path(meipass)

    # Common locations where PyInstaller places Tcl/Tk.
    # 1) <_MEIPASS>/tcl
    # 2) <_MEIPASS>/lib/tcl8.6 and <_MEIPASS>/lib/tk8.6
    candidates = [
        root / "tcl",
        root / "lib" / "tcl8.6",
        root / "lib" / "tk8.6",
    ]

    tcl_dir = None
    tk_dir = None

    # Prefer the lib/* layout first if present.
    if (root / "lib" / "tcl8.6").exists():
        tcl_dir = str(root / "lib" / "tcl8.6")
    if (root / "lib" / "tk8.6").exists():
        tk_dir = str(root / "lib" / "tk8.6")

    # Fallback to a flat tcl dir.
    if tcl_dir is None and (root / "tcl").exists():
        tcl_dir = str(root / "tcl")

    # Environment variables used by _tkinter/Tk to find scripts.
    _set_env_if_missing("TCL_LIBRARY", tcl_dir or "")
    _set_env_if_missing("TK_LIBRARY", tk_dir or "")

    # Also ensure candidate dirs are on PATH (helps locating dependent dlls).
    for p in candidates:
        if p.exists():
            _add_to_path(str(p))


_main()

