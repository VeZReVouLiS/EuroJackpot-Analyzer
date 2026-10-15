"""Bring the bundled draws file up to date (used by the GitHub workflow that publishes the web app).

Starts from app/seed/draws.json, downloads the newest draws and prize details with the same code the desktop app
uses, and writes the result.  If the online sources cannot be reached the seed is written unchanged.

Usage:  python -m tools.update_web_data --out data/draws.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from app import exporter, updater
from app.db import Database
from app.sources import importer

SEED = Path(__file__).resolve().parent.parent / "app" / "seed" / "draws.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out = Path(ap.parse_args().out)
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "web.db")
        db.upsert_draws(importer.parse_text(SEED.read_text(encoding="utf-8"), SEED.name))
        before = db.count()
        try:
            res = updater.update(db)
            print("update:", res)
        except Exception as e:  # noqa: BLE001  - keep going with what we have
            print(f"WARNING: could not update online ({type(e).__name__}: {e}); using the bundled draws", file=sys.stderr)
        draws = db.all_draws(with_details=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(json.loads(exporter.to_json(draws)), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")   # compact: it is downloaded by every phone
        print(f"wrote {out}: {len(draws)} draws ({len(draws) - before} new), last {draws[-1]['date']}")
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
