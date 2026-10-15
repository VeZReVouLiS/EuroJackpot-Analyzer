"""Remove the "Mark of the Web" (Zone.Identifier stream) from the app's own files.

A zip downloaded from the internet and extracted by Windows leaves every file flagged as "from the internet".
On some PCs the .NET loader then refuses Python.Runtime.dll and the native window cannot start
("Failed to resolve Python.Runtime.Loader.Initialize"). Equivalent of PowerShell's Unblock-File; must run
before pythonnet/webview is imported.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

STREAM = ":Zone.Identifier"


def unblock_tree(root: Path) -> int:
    """Strip the stream from every file below root. Returns the number of files unblocked."""
    count = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            try:
                os.remove(path + STREAM)
                count += 1
            except OSError:        # no such stream (the normal case) or not allowed: ignore
                pass
    return count


def unblock_app() -> int:
    """For the packaged Windows app: unblock its folder once, when it is flagged. Never raises."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return 0
    try:
        root = Path(sys.executable).resolve().parent
        probe = root / "_internal" / "pythonnet" / "runtime" / "Python.Runtime.dll"
        if probe.exists() and not os.path.exists(str(probe) + STREAM):
            return 0               # already clean: skip the walk
        return unblock_tree(root)
    except Exception:
        return 0
