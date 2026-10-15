import sys
from pathlib import Path


def base_dir() -> Path:
    """Folder next to the exe (portable) or project root in dev."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    p = base_dir() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_dir() -> Path:
    """Where bundled read-only resources (ui, locales) live."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", base_dir())) / "app"
    return Path(__file__).resolve().parent
