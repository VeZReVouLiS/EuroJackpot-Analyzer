import os

# EJP_VERSION_OVERRIDE: testing/docs only (e.g. pretend to be an older version to see the update screen)
__version__ = os.environ.get("EJP_VERSION_OVERRIDE") or "1.8.2"
APP_NAME = "EuroJackpot Analyzer"
# GitHub "owner/name" used for update checks (GitHub Releases). Empty = update check disabled.
GITHUB_REPO = "VeZReVouLiS/EuroJackpot-Analyzer"


def release_asset(platform_name: str | None = None, machine: str | None = None) -> str:
    """Name of the GitHub release asset for this platform (Windows portable zip, or the macOS app zip)."""
    import platform
    import sys

    if (platform_name or sys.platform) == "darwin":
        return "EuroJackpotApp-mac-" + ("arm64" if (machine or platform.machine()) == "arm64" else "intel") + ".zip"
    return "EuroJackpotApp-portable-win.zip"


RELEASE_ASSET = release_asset()
