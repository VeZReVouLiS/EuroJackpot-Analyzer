"""Statistics over the draw history.

Euro numbers: the pool was 1-8, then 1-10 (2014-10-10), then 1-12 (2022-03-25). Counts/gaps for a
euro number only consider draws in which that number was actually eligible.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from itertools import combinations

from . import rules

MAIN_RANGE = range(1, rules.MAIN_MAX + 1)
EURO_RANGE = range(1, 13)


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _number_stats(draws_all: list[dict], draws_win: list[dict], key: str, rng, eligible) -> list[dict]:
    """key: 'main'|'euro'. eligible(n, draw_date) -> bool."""
    # counts + eligible draws inside the window
    counts: Counter = Counter()
    elig_win: Counter = Counter()
    for d in draws_win:
        dd = _d(d["date"])
        for n in rng:
            if eligible(n, dd):
                elig_win[n] += 1
        counts.update(d[key])
    # gaps over the full history
    last_idx: dict[int, int] = {}
    max_gap: dict[int, int] = {}
    prev_idx: dict[int, int] = {}
    last_seen: dict[int, str] = {}
    first_elig: dict[int, int] = {}
    for i, d in enumerate(draws_all):
        dd = _d(d["date"])
        for n in rng:
            if n not in first_elig and eligible(n, dd):
                first_elig[n] = i
                prev_idx[n] = i - 1
        for n in d[key]:
            gap = i - prev_idx.get(n, i - 1) - 1
            max_gap[n] = max(max_gap.get(n, 0), gap)
            prev_idx[n] = i
            last_idx[n] = i
            last_seen[n] = d["date"]
    total = len(draws_all)
    out = []
    for n in rng:
        in_play = n in first_elig
        cur_gap = None
        if in_play:
            cur_gap = total - 1 - last_idx[n] if n in last_idx else total - first_elig[n]
            max_gap[n] = max(max_gap.get(n, 0), cur_gap)
        e = elig_win[n]
        c = counts[n]
        out.append({
            "n": n,
            "count": c,
            "eligible": e,
            "pct": round(100 * c / e, 2) if e else 0.0,   # % of eligible draws in which n came out
            "gap": cur_gap,                                # draws since last seen (full history)
            "max_gap": max_gap.get(n),
            "avg_gap": round(e / c, 1) if c else None,    # one appearance every N draws (window)
            "last_seen": last_seen.get(n),
            "active": eligible(n, date.max) if n <= 12 else False,
        })
    return out


def _euro_eligible(n: int, d: date) -> bool:
    return n <= rules.euro_max(d)


def _main_eligible(n: int, d: date) -> bool:
    return True


def _top(items: list[dict], field: str, reverse: bool, k: int = 10, only_active=False):
    pool = [i for i in items if i[field] is not None and (i.get("active", True) or not only_active)]
    pool.sort(key=lambda i: (i[field], i["n"]), reverse=reverse)
    return [i["n"] for i in pool[:k]]


def _ranked(block: list[dict], only_active: bool):
    return {
        "hot": _top(block, "pct", True, only_active=only_active),
        "cold": _top(block, "pct", False, only_active=only_active),
        "overdue": _top(block, "gap", True, only_active=only_active),
    }


def compute(draws: list[dict], since: str | None = None, until: str | None = None) -> dict:
    """draws sorted ascending by date. since/until: 'YYYY-MM-DD' window for counts."""
    draws = sorted(draws, key=lambda d: d["date"])
    win = [d for d in draws if (not since or d["date"] >= since) and (not until or d["date"] <= until)]
    # gaps are always measured on history up to `until` (default: everything)
    hist = [d for d in draws if not until or d["date"] <= until]
    main = _number_stats(hist, win, "main", MAIN_RANGE, _main_eligible)
    euro = _number_stats(hist, win, "euro", EURO_RANGE, _euro_eligible)
    for e in euro:
        e["active"] = e["n"] <= rules.current_euro_max()

    odd_dist = Counter(sum(n % 2 for n in d["main"]) for d in win)
    low_dist = Counter(sum(n <= 25 for n in d["main"]) for d in win)
    sums = Counter((sum(d["main"]) // 10) * 10 for d in win)
    pairs = Counter()
    for d in win:
        pairs.update(combinations(sorted(d["main"]), 2))
    sum_values = [sum(d["main"]) for d in win]

    return {
        "n_draws": len(win),
        "n_total": len(hist),
        "first_date": win[0]["date"] if win else None,
        "last_date": win[-1]["date"] if win else None,
        "last_draw": hist[-1] if hist else None,
        "main": main,
        "euro": euro,
        "ranking": {"main": _ranked(main, False), "euro": _ranked(euro, True)},
        "odd_even": [{"odd": k, "even": 5 - k, "count": odd_dist.get(k, 0)} for k in range(6)],
        "low_high": [{"low": k, "high": 5 - k, "count": low_dist.get(k, 0)} for k in range(6)],
        "sum_hist": [{"from": s, "count": sums.get(s, 0)} for s in range(10, 250, 10)],
        "sum_avg": round(sum(sum_values) / len(sum_values), 1) if sum_values else None,
        "top_pairs": [{"pair": list(p), "count": c} for p, c in pairs.most_common(10)],
    }
