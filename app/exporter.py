"""Export the stored draws so they can be imported into another copy of the app (even offline)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from . import version

FORMAT = "eurojackpot-analyzer"


def to_json(draws: list[dict]) -> str:
    """Full-fidelity export (includes prize details). Re-importable by importer.parse_text."""
    doc = {
        "format": FORMAT,
        "version": 1,
        "app_version": version.__version__,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(draws),
        "draws": draws,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1)


def to_csv(draws: list[dict]) -> str:
    """Simple numbers-only export: date;n1..n5;e1;e2 (opens in Excel, importable)."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    w.writerow(["date", "n1", "n2", "n3", "n4", "n5", "e1", "e2"])
    for d in draws:
        w.writerow([d["date"], *d["main"], *d["euro"]])
    return out.getvalue()


def default_filename(fmt: str) -> str:
    return f"eurojackpot-draws-{datetime.now():%Y-%m-%d}.{fmt}"
