"""Golden file for the JavaScript port (web/tests): results of the Python implementation for the same inputs.

Usage:  python -m tools.make_golden        (rewrites web/tests/golden.json; the JS tests compare against it)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from app import evaluation, exporter, rules, stats
from app.sources import importer

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "app" / "seed" / "draws.json"
OUT = ROOT / "web" / "tests" / "golden.json"

SAMPLES = {
    "csv_semicolon": "date;n1;n2;n3;n4;n5;e1;e2\n2026-10-13;11;17;20;22;35;4;8\n2026-10-09;18;38;41;43;46;7;10\n",
    "csv_greek_dates": "Ημερομηνία,Αριθμοί\n13/10/2026,\"35 20 22 17 11 + 4 8\"\n09.10.2026,\"46 43 41 38 18 + 10 7\"\n",
    "csv_no_header": "13/10/2026,11,17,20,22,35,4,8\n20261009,18,38,41,43,46,7,10\n",
    "json_list": '[{"date":"2026-10-13","numbers":[11,17,20,22,35],"euro":[4,8]},{"date":"2026-10-09","main":[18,38,41,43,46],"euro_numbers":[7,10]}]',
    "json_export": json.dumps({"format": "eurojackpot-analyzer", "draws": [{"date": "2026-10-13", "main": [11, 17, 20, 22, 35], "euro": [4, 8], "source": "x", "details": {"v": 2, "classes": []}}]}),
    "invalid": "foo,bar\n1,2\n",
}


def _stats_view(s: dict) -> dict:
    keep = ("n", "count", "eligible", "pct", "gap", "max_gap", "avg_gap", "last_seen", "active")
    return {
        "n_draws": s["n_draws"], "n_total": s["n_total"], "first_date": s["first_date"], "last_date": s["last_date"],
        "main": [{k: x[k] for k in keep} for x in s["main"]], "euro": [{k: x[k] for k in keep} for x in s["euro"]],
        "ranking": s["ranking"], "odd_even": s["odd_even"], "low_high": s["low_high"], "sum_hist": s["sum_hist"],
        "sum_avg": s["sum_avg"], "top_pairs": s["top_pairs"],
    }


def main() -> None:
    seed = json.loads(SEED.read_text(encoding="utf-8"))["draws"]
    draws = sorted(seed, key=lambda d: d["date"])
    last = draws[-1]["date"]
    periods = {"all": (None, None), "1y": ((date.fromisoformat(last) - timedelta(days=365)).isoformat(), None),
               "5y": ((date.fromisoformat(last) - timedelta(days=365 * 5)).isoformat(), None),
               "last:100": (draws[-100]["date"], None), "last:50": (draws[-50]["date"], None)}
    gold: dict = {"seed_count": len(draws), "stats": {}, "evaluation": [], "import": {}, "next_draws": [], "csv": None}
    for name, (since, until) in periods.items():
        gold["stats"][name] = {"since": since, "until": until, "result": _stats_view(stats.compute(draws, since, until))}
    # evaluation: fixed columns against draws with prize details and without
    cols = [{"main": [11, 17, 20, 22, 35], "euro": [4, 8]}, {"main": [11, 17, 20, 40, 41], "euro": [4, 1]},
            {"main": [1, 2, 3, 4, 5], "euro": [1, 2]}, {"main": [11, 17, 40, 41, 42], "euro": [8, 9]},
            {"main": [20, 22, 35, 47, 48], "euro": [5, 6]}, {"main": [11, 40, 41, 42, 43], "euro": [4, 8]}]
    for d in (draws[-1], draws[-2], draws[-40], {**draws[-3], "details": None}):
        gold["evaluation"].append({"draw": d, "result": evaluation.evaluate_ticket(cols, d), "columns": cols})
    for k, text in SAMPLES.items():
        try:
            gold["import"][k] = [{"date": r["date"], "main": r["main"], "euro": r["euro"]} for r in importer.parse_text(text, "x.json" if k.startswith("json") else "x.csv")]
        except Exception as e:  # noqa: BLE001
            gold["import"][k] = "error"
    gold["samples"] = SAMPLES
    for stamp in ("2026-10-13T10:00", "2026-10-13T21:14", "2026-10-13T21:15", "2026-10-16T22:00", "2022-03-25T09:00", "2022-03-28T12:00", "2026-12-31T08:30"):
        now = datetime.fromisoformat(stamp)
        gold["next_draws"].append({"now": stamp, "dates": [x.isoformat() for x in rules.next_draw_dates(now, 4)]})
    gold["csv"] = exporter.to_csv(draws[-3:])
    gold["csv_input"] = draws[-3:]
    OUT.write_text(json.dumps(gold, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
