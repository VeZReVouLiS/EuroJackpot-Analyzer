"""Cross-check generated tickets against a draw: matches, prize tier and prize amount."""
from __future__ import annotations

# Tiers that pay a prize in the current 5/50 + 2/12 format (the 1+1 tier is the Greek add-on, 2024+ only)
PRIZE_TIERS = {"5+2", "5+1", "5+0", "4+2", "4+1", "4+0", "3+2", "3+1", "3+0", "2+2", "2+1", "1+2"}


def tier_of(main_hits: int, euro_hits: int) -> str:
    return f"{main_hits}+{euro_hits}"


def evaluate_column(col: dict, draw: dict) -> dict:
    main_hit = sorted(set(col["main"]) & set(draw["main"]))
    euro_hit = sorted(set(col["euro"]) & set(draw["euro"]))
    tier = tier_of(len(main_hit), len(euro_hit))
    prize, known, wins = 0.0, True, False
    classes = {c["tier"]: c for c in ((draw.get("details") or {}).get("classes") or [])}
    if draw.get("details"):
        c = classes.get(tier)
        if c and c.get("prize", 0) > 0:
            prize, wins = float(c["prize"]), True
    else:                                   # no prize table for this draw (imported without details)
        known = False
        wins = tier in PRIZE_TIERS
    return {"main_hit": main_hit, "euro_hit": euro_hit, "tier": tier, "prize": round(prize, 2), "wins": wins,
            "known": known}


def evaluate_ticket(columns: list[dict], draw: dict) -> dict:
    cols = [evaluate_column(c, draw) for c in columns]
    return {
        "draw_date": draw["date"],
        "draw": {"main": draw["main"], "euro": draw["euro"]},
        "columns": cols,
        "total_prize": round(sum(c["prize"] for c in cols), 2),
        "winning_columns": sum(1 for c in cols if c["wins"]),
        "complete": all(c["known"] for c in cols),
    }
