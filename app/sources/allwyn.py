"""Allwyn (ex-OPAP) draws API. EuroJackpot = game 5149, available only since 2024-03-08 (Greece joined).

Besides the numbers it provides the winners in Greece per prize class (``winners``) next to the total
across all countries (``winnersAll``), so it enriches the details of the official data.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from .http import get_json

BASE = "https://api.opap.gr/draws/v3.0/5149"
REFERER = "https://www.allwyn.gr/"
FIRST_DATE = date(2024, 3, 8)

# Allwyn prize category id -> tier label (same order as the official classes in the 1-12 era)
TIERS = {1: "5+2", 2: "5+1", 3: "5+0", 4: "4+2", 5: "4+1", 6: "3+2", 7: "4+0", 8: "2+2",
         9: "3+1", 10: "3+0", 11: "1+2", 12: "2+1"}
GREEK_ADDON_TIER = "1+1"   # Greek-only category (add-on 0.50 EUR)


def _get(path: str):
    return get_json(f"{BASE}/{path}", REFERER)


def _details(draw: dict) -> dict:
    classes = []
    for p in draw.get("prizeCategories") or []:
        cid = p.get("id")
        if p.get("gameType") == "EJKAddon" or cid == 13:
            classes.append({"cls": 13, "tier": GREEK_ADDON_TIER, "winners": int(p.get("winners") or 0),
                            "winners_gr": int(p.get("winners") or 0), "prize": float(p.get("divident") or 0),
                            "greek_only": True})
        elif cid in TIERS:
            classes.append({"cls": cid, "tier": TIERS[cid], "winners": int(p.get("winnersAll") or 0),
                            "winners_gr": int(p.get("winners") or 0), "prize": float(p.get("divident") or 0)})
    ws = draw.get("wagerStatistics") or {}
    return {"classes": classes, "columns_gr": ws.get("columns"), "columns_all": ws.get("totalColumnsAll"),
            "stake_all": ws.get("totalSalesAll"), "draw_no": draw.get("drawId")}


def parse(draw: dict) -> dict | None:
    """Convert one Allwyn draw JSON into our draw dict (None when results are not available)."""
    if not draw or draw.get("status") != "results":
        return None
    wn = draw.get("winningNumbers") or {}
    main, euro = wn.get("list") or [], wn.get("bonus") or []
    if len(main) != 5 or len(euro) != 2:
        return None
    # draws take place ~21:00 Greek/Finnish time (UTC+2/+3): +3h keeps the correct calendar day
    dt = datetime.fromtimestamp(draw["drawTime"] / 1000, tz=timezone.utc) + timedelta(hours=3)
    return {"date": dt.date().isoformat(), "main": sorted(main), "euro": sorted(euro),
            "source": "allwyn.gr", "details": _details(draw)}


def fetch_draw(draw_id: int) -> dict | None:
    return parse(_get(str(draw_id)))


def fetch_range(start: date, end: date, workers: int = 4) -> list[dict]:
    start = max(start, FIRST_DATE)
    if start > end:
        return []
    ids: list[int] = []
    cur = date(start.year, start.month, 1)      # the API is queried month by month
    while cur <= end:
        nxt = date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
        last = nxt - timedelta(days=1)
        ids.extend(_get(f"draw-date/{cur.isoformat()}/{last.isoformat()}/draw-id") or [])
        cur = nxt
    with ThreadPoolExecutor(max_workers=workers) as ex:
        draws = [d for d in ex.map(fetch_draw, ids) if d]
    return [d for d in draws if start.isoformat() <= d["date"] <= end.isoformat()]


def last_draw() -> dict | None:
    res = _get("last-result-and-active")
    return parse(res["last"]) if res and res.get("last") else None


def merge_details(official: dict | None, allwyn: dict | None) -> dict | None:
    """Official classes (all countries) + Greek winners / extras from Allwyn."""
    if not official:
        return allwyn
    if not allwyn:
        return official
    out = dict(official)
    gr = {c["tier"]: c for c in allwyn["classes"]}
    merged = []
    for c in official["classes"]:
        a = gr.get(c["tier"])
        merged.append({**c, "winners_gr": a["winners_gr"]} if a else dict(c))
    for c in allwyn["classes"]:
        if c.get("greek_only"):
            merged.append(c)
    out["classes"] = merged
    for k in ("columns_gr", "columns_all", "draw_no"):
        out[k] = allwyn.get(k)
    out["stake_all"] = out.get("stake_all") or allwyn.get("stake_all")
    return out
