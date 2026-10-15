"""Updating the *application itself* from GitHub Releases (separate from draw-data updates).

Release layout expected on GitHub:
    tag  vX.Y.Z
    asset EuroJackpotApp-portable-win.zip          (folder EuroJackpotApp/ with the exe)
    asset EuroJackpotApp-mac-arm64.zip / EuroJackpotApp-mac-intel.zip   (the .app, made with `ditto -c -k --keepParent`)
    asset <zip>.sha256                             ("<hex>  <filename>")
The install is refused unless the SHA-256 of the downloaded zip matches.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from . import tls, version
from .paths import app_bundle, base_dir, is_mac_app

API = "https://api.github.com/repos/{repo}/releases/latest"
UA = f"EuroJackpotAnalyzer/{version.__version__}"


class AppUpdateError(Exception):
    pass


def parse_version(s: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", s.split("-")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def _open(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout, context=tls.context())


def pick_assets(release: dict, repo: str) -> tuple[str | None, str | None]:
    """Return (zip_url, sha256_url) – only URLs that belong to this repo's releases are accepted."""
    prefix = f"https://github.com/{repo}/releases/download/"
    zip_url = sha_url = None
    for a in release.get("assets", []):
        url = a.get("browser_download_url", "")
        if not url.startswith(prefix):
            continue
        if a.get("name") == version.RELEASE_ASSET:
            zip_url = url
        elif a.get("name") == version.RELEASE_ASSET + ".sha256":
            sha_url = url
    return zip_url, sha_url


def check(repo: str | None = None) -> dict:
    """Ask GitHub for the latest release. Never raises; errors are returned in ``error``."""
    repo = repo if repo is not None else version.GITHUB_REPO
    res = {"current": version.__version__, "latest": None, "newer": False, "notes": "", "url": None,
           "installable": False, "error": None, "configured": bool(repo)}
    if not repo:
        return res
    try:
        with _open(API.format(repo=repo)) as r:
            rel = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        res["error"] = "no releases yet" if e.code == 404 else f"HTTP {e.code} {e.reason}"
        return res
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
        return res
    tag = rel.get("tag_name", "")
    zip_url, sha_url = pick_assets(rel, repo)
    res.update(latest=tag.lstrip("v"), newer=is_newer(tag, version.__version__), notes=rel.get("body") or "",
               url=rel.get("html_url"), installable=bool(zip_url and sha_url and can_install()),
               zip_url=zip_url, sha_url=sha_url)
    return res


def can_install() -> bool:
    """In-app install works for the packaged app; on macOS only when the .app can be replaced (writable folder)."""
    if not getattr(sys, "frozen", False):
        return False
    if is_mac_app():
        bundle = app_bundle()
        return bool(bundle and bundle.suffix == ".app" and os.access(bundle.parent, os.W_OK))
    return True


def extract_mac(zip_path: Path, dest: Path) -> Path:
    """Unpack a macOS app zip with ditto (keeps symlinks and permissions; Python's zipfile would not)."""
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", "-x", "-k", str(zip_path), str(dest)], check=True, capture_output=True)
    apps = [p for p in dest.iterdir() if p.suffix == ".app" and p.is_dir()]
    if len(apps) != 1:
        raise AppUpdateError("archive does not contain exactly one .app")
    return apps[0]


APPLY_SH = """#!/bin/sh
# usage: apply.sh <pid> <new .app> <installed .app>
while kill -0 "$1" 2>/dev/null; do sleep 0.5; done
sleep 1
rm -rf "$3.old"
mv "$3" "$3.old" || exit 1
if ditto "$2" "$3"; then
  rm -rf "$3.old"
  xattr -dr com.apple.quarantine "$3" 2>/dev/null
else
  rm -rf "$3"
  mv "$3.old" "$3"
fi
open "$3"
"""


def expected_sha256(text: str) -> str:
    m = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if not m:
        raise AppUpdateError("checksum file is invalid")
    return m.group(1).lower()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_extract(zip_path: Path, dest: Path) -> Path:
    """Extract refusing path traversal; returns the folder that contains the exe."""
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            target = (dest / name).resolve()
            if dest != target and dest not in target.parents:
                raise AppUpdateError(f"unsafe path in archive: {name}")
        z.extractall(dest)
    exes = list(dest.rglob("EuroJackpotApp.exe"))
    if not exes:
        raise AppUpdateError("archive does not contain EuroJackpotApp.exe")
    return exes[0].parent


APPLY_PS1 = r"""param([int]$ProcId, [string]$Src, [string]$Dst, [string]$Exe)
Start-Transcript -Path (Join-Path $PSScriptRoot 'apply.log') | Out-Null
try { Wait-Process -Id $ProcId -Timeout 90 -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 1
robocopy $Src $Dst /E /XD "$Dst\data" /R:10 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
"robocopy exit code: $LASTEXITCODE"
Start-Process -FilePath $Exe
Stop-Transcript | Out-Null
"""


def install(release: dict, progress=None) -> None:
    """Download, verify and schedule the replacement of the running app (frozen builds only)."""
    if not can_install():
        raise AppUpdateError("in-app install works only in the packaged app (with a writable install folder)")
    zip_url, sha_url = release.get("zip_url"), release.get("sha_url")
    if not zip_url or not sha_url:
        raise AppUpdateError("release has no installable package")
    tmp = Path(tempfile.mkdtemp(prefix="ejp_update_"))
    try:
        with _open(sha_url) as r:
            want = expected_sha256(r.read().decode("utf-8", "ignore"))
        pkg = tmp / "pkg.zip"
        with _open(zip_url, timeout=60) as r, open(pkg, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1 << 16):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if sha256_file(pkg) != want:
            raise AppUpdateError("checksum mismatch - download discarded")
        src = extract_mac(pkg, tmp / "new") if is_mac_app() else safe_extract(pkg, tmp / "new")
    except AppUpdateError:
        raise
    except Exception as e:
        raise AppUpdateError(f"{type(e).__name__}: {getattr(e, 'reason', e)}") from e
    if is_mac_app():
        script = tmp / "apply.sh"
        script.write_text(APPLY_SH, encoding="utf-8")
        log = open(tmp / "apply.log", "w")
        subprocess.Popen(["/bin/sh", str(script), str(os.getpid()), str(src), str(app_bundle())],
                         stdout=log, stderr=log, start_new_session=True, close_fds=True)
        return
    ps1 = tmp / "apply.ps1"
    ps1.write_text(APPLY_PS1, encoding="utf-8")
    exe = Path(sys.executable).resolve()
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(ps1),
           "-ProcId", str(os.getpid()), "-Src", str(src), "-Dst", str(base_dir()), "-Exe", str(exe)]
    base = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    breakaway = 0x01000000          # CREATE_BREAKAWAY_FROM_JOB: survive if our job object is closed with us
    try:
        subprocess.Popen(cmd, creationflags=base | breakaway, close_fds=True)
    except OSError:                 # the job does not allow breakaway
        subprocess.Popen(cmd, creationflags=base, close_fds=True)
