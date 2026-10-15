"""Copy the pure-Python core (rules, stats, generators) and a compact numbers-only history into the
Home Assistant integration repo, so both projects use identical logic.

Usage:  python -m tools.sync_ha_core C:\\path\\to\\EuroJackpot-Analyzer-HA
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
CORE_FILES = ["rules.py", "stats.py", "generators.py"]


def main(ha_repo: str) -> None:
    comp = Path(ha_repo) / "custom_components" / "eurojackpot_analyzer"
    core = comp / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / "__init__.py").write_text('"""Vendored from EuroJackpot-Analyzer (tools/sync_ha_core.py). Do not edit here."""\n',
                                      encoding="utf-8")
    for name in CORE_FILES:
        text = (APP / name).read_text(encoding="utf-8")
        (core / name).write_text("# Vendored copy of EuroJackpot-Analyzer/app/" + name + " - edit it there.\n" + text,
                                 encoding="utf-8")
    seed = json.loads((APP / "seed" / "draws.json").read_text(encoding="utf-8"))
    compact = [[d["date"], d["main"], d["euro"]] for d in seed["draws"]]
    out = comp / "data" / "draws.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"version": 1, "draws": compact}, separators=(",", ":")), encoding="utf-8")
    # country/language catalogue, flags and logo for the HA panel (served from www/assets)
    assets = comp / "www" / "assets"
    shutil.rmtree(assets, ignore_errors=True)
    (assets / "flags").mkdir(parents=True)
    shutil.copy(APP / "ui" / "countries.json", assets / "countries.json")
    shutil.copy(APP / "ui" / "logo.svg", assets / "logo.svg")
    for f in (APP / "ui" / "flags").iterdir():
        shutil.copy(f, assets / "flags" / f.name)
    print(f"synced {len(CORE_FILES)} core files and {len(compact)} draws ({out.stat().st_size // 1024} KB) -> {comp}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
