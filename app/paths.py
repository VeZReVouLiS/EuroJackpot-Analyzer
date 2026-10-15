import sys
from pathlib import Path

MAC_DATA_NAME = "EuroJackpot Analyzer"


def is_mac_app() -> bool:
    """True when running as the packaged macOS app (EuroJackpot Analyzer.app)."""
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


def app_bundle() -> Path | None:
    """The .app folder of the packaged macOS app (executable = X.app/Contents/MacOS/X)."""
    if not is_mac_app():
        return None
    return Path(sys.executable).resolve().parents[2]


def base_dir() -> Path:
    """Folder next to the exe (portable) or project root in dev."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Windows: the `data` folder next to the exe (portable). macOS app: ~/Library/Application Support,
    because an .app bundle must not be written to (and is replaced on every update)."""
    if is_mac_app():
        p = Path.home() / "Library" / "Application Support" / MAC_DATA_NAME
    else:
        p = base_dir() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resource_dir() -> Path:
    """Where bundled read-only resources (ui, locales) live."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", base_dir())) / "app"
    return Path(__file__).resolve().parent
