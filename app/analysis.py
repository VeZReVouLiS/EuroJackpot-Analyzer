"""Analysis of a ticket: exact win probabilities, expected prize, the statistical profile of every column and a
"what would it have won in all past draws" check.

Nothing here predicts a draw. In a fair lottery every column has exactly the same chance; the profile and the
history check are informational. The expected prize uses the average of the real prizes of the last years
(the jackpot class is left out of it: one or two draws decide it).
"""
from __future__ import annotations

from math import comb

from . import rules

MAIN_POOL, MAIN_PICK, EURO_PICK = rules.MAIN_MAX, rules.MAIN_COUNT, rules.EURO_COUNT
EURO_POOL = rules.current_euro_max()
# the twelve classes of the current 5/50 + 2/12 game, in the order of the official table
TIERS = ["5+2", "5+1", "5+0", "4+2", "4+1", "3+2", "4+0", "2+2", "3+1", "3+0", "1+2", "2+1"]
GREEK_TIER = "1+1"           # Greek add-on class
AVG_SINCE = "2022-03-29"     # since the euro pool is 1-12 and there are two draws a week
TYPICAL = {"odd": (2, 3), "low": (2, 3), "sum": (90, 160), "consecutive": 1}      # same shape as the "smart" algorithm


def tier_probability(main: int, euro: int) -> float:
    """Probability that one column has exactly `main` main numbers and `euro` Euro numbers right."""
    pm = comb(MAIN_PICK, main) * comb(MAIN_POOL - MAIN_PICK, MAIN_PICK - main) / comb(MAIN_POOL, MAIN_PICK)
    pe = comb(EURO_PICK, euro) * comb(EURO_POOL - EURO_PICK, EURO_PICK - euro) / comb(EURO_POOL, EURO_PICK)
    return pm * pe


def tier_probabilities(country: str = "") -> dict[str, float]:
    out = {t: tier_probability(int(t[0]), int(t[2])) for t in TIERS}
    if country == "GR":
        out[GREEK_TIER] = tier_probability(1, 1)
    return out


def average_prizes(draws: list[dict], since: str = AVG_SINCE) -> dict[str, float]:
    """Mean prize per class over the draws since `since` that paid something in that class."""
    acc: dict[str, list[float]] = {}
    for d in draws:
        if d["date"] < since or not d.get("details"):
            continue
        for c in d["details"].get("classes", []):
            if c.get("prize", 0) > 0:
                acc.setdefault(c["tier"], []).append(float(c["prize"]))
    return {t: sum(v) / len(v) for t, v in acc.items()}


def _profile(col: dict, st: dict) -> dict:
    main = sorted(col["main"])
    mm = {x["n"]: x for x in st["main"]}
    em = {x["n"]: x for x in st["euro"]}
    base = sum(x["pct"] for x in st["main"]) / len(st["main"])           # average frequency of a main number, %
    base_e = sum(x["pct"] for x in st["euro"] if x["active"]) / max(1, sum(1 for x in st["euro"] if x["active"]))
    freq = [mm[n]["pct"] for n in main]
    gaps = [mm[n]["gap"] or 0 for n in main]
    odd = sum(n % 2 for n in main)
    low = sum(n <= 25 for n in main)
    consec = sum(1 for a, b in zip(main, main[1:]) if b == a + 1)
    total = sum(main)
    typical = (TYPICAL["odd"][0] <= odd <= TYPICAL["odd"][1] and TYPICAL["low"][0] <= low <= TYPICAL["low"][1]
               and TYPICAL["sum"][0] <= total <= TYPICAL["sum"][1] and consec <= TYPICAL["consecutive"])
    hot = sorted(main, key=lambda n: (-mm[n]["pct"], n))[:2]
    overdue = sorted(main, key=lambda n: (-(mm[n]["gap"] or 0), n))[:2]
    return {
        "freq_ratio": round(sum(freq) / len(freq) / base, 3) if base else None,      # 1.0 = as frequent as average
        "euro_freq_ratio": round(sum(em[n]["pct"] for n in col["euro"]) / len(col["euro"]) / base_e, 3) if base_e else None,
        "avg_gap": round(sum(gaps) / len(gaps), 1),
        "hottest": hot, "most_overdue": overdue,
        "odd": odd, "even": MAIN_PICK - odd, "low": low, "high": MAIN_PICK - low,
        "sum": total, "consecutive": consec, "typical": typical,
    }


def backtest(columns: list[dict], draws: list[dict], country: str = "", price: float = rules.COLUMN_PRICE) -> list[dict]:
    """For every column: the draws in which it would have won something, with the prize of that draw."""
    out = []
    for col in columns:
        wins, tiers, total, known_all = [], {}, 0.0, True
        ms, es = set(col["main"]), set(col["euro"])
        for d in draws:
            m, e = len(ms & set(d["main"])), len(es & set(d["euro"]))
            tier = f"{m}+{e}"
            if tier == GREEK_TIER and country != "GR":
                continue
            classes = {c["tier"]: c for c in ((d.get("details") or {}).get("classes") or [])}
            if d.get("details"):
                c = classes.get(tier)
                if not c or not c.get("prize", 0) > 0:
                    continue
                prize, known = float(c["prize"]), True
            else:
                if tier not in TIERS:
                    continue
                prize, known = 0.0, False
                known_all = False
            wins.append({"date": d["date"], "tier": tier, "prize": round(prize, 2), "known": known})
            tiers[tier] = tiers.get(tier, 0) + 1
            total += prize
        best = next((t for t in TIERS + [GREEK_TIER] if t in tiers), None)
        out.append({"draws": len(draws), "cost": round(len(draws) * price, 2), "wins": wins, "tiers": tiers, "best_tier": best,
                    "total_prize": round(total, 2), "complete": known_all, "draws_with_win": len(wins)})
    return out


def analyze(columns: list[dict], draws: list[dict], st: dict, price: float, country: str = "") -> dict:
    """Full analysis of a ticket (a list of columns {main, euro}) against the stored draws."""
    probs = tier_probabilities(country)
    avg = average_prizes(draws)
    p_any = sum(probs.values())
    ev_col = sum(p * avg.get(t, 0.0) for t, p in probs.items() if t != "5+2")        # jackpot class left out
    n = len(columns)
    bt = backtest(columns, draws, country, price)
    cols = []
    for col, b in zip(columns, bt):
        cols.append({"main": sorted(col["main"]), "euro": sorted(col["euro"]), "profile": _profile(col, st), "backtest": b,
                     "p_any": p_any, "odds_any": round(1 / p_any, 1)})
    p_ticket = 1 - (1 - p_any) ** n
    p_jackpot = n * probs["5+2"]
    cost = round(n * price, 2)
    ev = round(n * ev_col, 2)
    table = [{"tier": t, "p": probs[t], "odds": round(1 / probs[t], 1), "avg_prize": round(avg.get(t, 0.0), 2)} for t in probs]
    return {
        "columns": cols,
        "overall": {
            "columns": n, "price": price, "cost": cost, "p_any": p_ticket, "odds_any": round(1 / p_ticket, 1),
            "p_jackpot": p_jackpot, "odds_jackpot": round(1 / p_jackpot), "expected_prize": ev, "expected_net": round(ev - cost, 2),
            "ev_per_column": round(ev_col, 4), "tiers": table,
            "backtest": {"draws": len(draws), "cost": round(sum(b["cost"] for b in bt), 2), "total_prize": round(sum(b["total_prize"] for b in bt), 2),
                         "columns_with_win": sum(1 for b in bt if b["wins"])},
        },
        "country": country,
    }
