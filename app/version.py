import os

# EJP_VERSION_OVERRIDE: testing/docs only (e.g. pretend to be an older version to see the update screen)
__version__ = os.environ.get("EJP_VERSION_OVERRIDE") or "1.3.1"
APP_NAME = "EuroJackpot Analyzer"
# GitHub "owner/name" used for update checks (GitHub Releases). Empty = update check disabled.
GITHUB_REPO = "VeZReVouLiS/EuroJackpot-Analyzer"
RELEASE_ASSET = "EuroJackpotApp-portable-win.zip"
