import json
import re

from tools import build_site


def test_site_has_everything_a_phone_needs(tmp_path):
    out = build_site.build(tmp_path / "site", build_site.ROOT / "app" / "seed" / "draws.json", "9.9.9")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "web/boot.js" in html and "manifest.webmanifest" in html and "viewport-fit=cover" in html
    manifest = json.loads((out / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone" and all((out / i["src"]).exists() for i in manifest["icons"])
    assert json.loads((out / "version.json").read_text(encoding="utf-8"))["version"] == "9.9.9"
    assert 'VERSION = "9.9.9"' in (out / "web" / "version.js").read_text(encoding="utf-8")
    sw = (out / "sw.js").read_text(encoding="utf-8")
    precache = json.loads(re.search(r"const PRECACHE = (\[.*?\]);", sw, re.S).group(1))
    for must in ("./", "index.html", "app.js", "web/core.js", "web/webapi.js", "data/draws.json", "locales/de.json", "countries.json", "flags/gr.svg"):
        assert must in precache, must
    assert all((out / p).exists() for p in precache if p != "./")
    assert not (out / "icon.ico").exists()


def test_web_scripts_import_only_what_exists(tmp_path):
    out = build_site.build(tmp_path / "site", build_site.ROOT / "app" / "seed" / "draws.json", "1.0.0")
    for js in (out / "web").glob("*.js"):
        for rel in re.findall(r'from "(\./[^"]+)"', js.read_text(encoding="utf-8")):
            assert (js.parent / rel).exists(), f"{js.name} imports {rel}"
