import subprocess
import sys
from pathlib import Path

from app import appupdate, paths, version


def test_release_asset_names():
    assert version.release_asset("win32") == "EuroJackpotApp-portable-win.zip"
    assert version.release_asset("darwin", "arm64") == "EuroJackpotApp-mac-arm64.zip"
    assert version.release_asset("darwin", "x86_64") == "EuroJackpotApp-mac-intel.zip"


def test_mac_app_keeps_its_data_outside_the_bundle(tmp_path, monkeypatch):
    exe = tmp_path / "EuroJackpot Analyzer.app" / "Contents" / "MacOS" / "EuroJackpot Analyzer"
    exe.parent.mkdir(parents=True)
    exe.write_text("x")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    assert paths.is_mac_app() and paths.app_bundle() == exe.parents[2]
    assert paths.data_dir() == tmp_path / "home" / "Library" / "Application Support" / "EuroJackpot Analyzer"
    assert paths.data_dir().is_dir()


def test_windows_data_stays_portable(tmp_path, monkeypatch):
    exe = tmp_path / "EuroJackpotApp.exe"
    exe.write_text("x")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert not paths.is_mac_app() and paths.data_dir() == tmp_path / "data"


def test_apply_script_is_valid_sh():
    import shutil

    sh = shutil.which("sh")
    if not sh:
        return
    r = subprocess.run([sh, "-n", "-c", appupdate.APPLY_SH], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_tls_context_includes_the_certifi_bundle():
    import ssl

    from app import tls

    ctx = tls.context()
    assert isinstance(ctx, ssl.SSLContext) and ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.cert_store_stats()["x509_ca"] > 50          # roots are loaded (certifi on a bare macOS Python)
