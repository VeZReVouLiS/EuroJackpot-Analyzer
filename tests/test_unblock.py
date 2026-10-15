import sys

import pytest

from app import unblock

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="NTFS alternate streams are Windows only")


def mark(path):
    with open(str(path) + ":Zone.Identifier", "w") as f:
        f.write("[ZoneTransfer]\r\nZoneId=3\r\n")


def test_unblock_tree_removes_zone_stream(tmp_path):
    sub = tmp_path / "_internal" / "pythonnet" / "runtime"
    sub.mkdir(parents=True)
    files = [tmp_path / "a.exe", sub / "Python.Runtime.dll", sub / "b.txt"]
    for f in files:
        f.write_text("x")
    for f in files[:2]:
        mark(f)
    assert all(__import__("os").path.exists(str(f) + ":Zone.Identifier") for f in files[:2])
    assert unblock.unblock_tree(tmp_path) == 2
    assert not any(__import__("os").path.exists(str(f) + ":Zone.Identifier") for f in files)
    assert files[1].read_text() == "x"            # the file itself is untouched
    assert unblock.unblock_tree(tmp_path) == 0    # idempotent


def test_unblock_app_noop_when_not_frozen(tmp_path):
    assert unblock.unblock_app() == 0
