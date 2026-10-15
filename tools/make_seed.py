"""Build the offline snapshot bundled with the app: app/seed/draws.json.

Run before every release:  python -m tools.make_seed
It downloads the full history (with prize details) into a throw-away database and exports it.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from app import exporter, updater
from app.db import Database

OUT = Path(__file__).resolve().parent.parent / "app" / "seed" / "draws.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "seed.db")
        last = [0]

        def prog(done, total):
            if done - last[0] >= 100 or done == total:
                last[0] = done
                print(f"  {done}/{total}", flush=True)

        res = updater.update(db, prog)
        print(res)
        draws = db.all_draws(with_details=True)
        missing = sum(1 for d in draws if not d.get("details"))
        if missing:
            print(f"WARNING: {missing} draws without details", file=sys.stderr)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(exporter.to_json(draws), encoding="utf-8")
        print(f"wrote {OUT} ({len(draws)} draws, {OUT.stat().st_size // 1024} KB)")
        db.close()


if __name__ == "__main__":
    main()
