"""Official EuroJackpot results (Lotto Hessen WL_InfoService) - full history since 2012-03-23."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Callable

from .. import rules
from .http import SourceError, get_json

URL = (
    "https://www.eurojackpot.com/wlinfo/WL_InfoService"
    "?client=jsn&gruppe=ZahlenUndQuoten&spielart=EJ&adg=ja&datum={d}"
)
DETAILS_VERSION = 2     # 2 = adds "where" (winners per country / German state) to the top classes
REFERER = "https://www.eurojackpot.com/"


def _where(aufteilung) -> list[dict]:
    """Where the winners of a class are: [{"alpha3","code","winners","region"?}] (Germany is split by state)."""
    out = []
    for a in aufteilung or []:
        try:
            item = {"alpha3": str(a["landAlpha3"]), "code": str(a.get("kuerzel") or ""), "winners": int(a["anzahl"])}
        except (KeyError, TypeError, ValueError):
            continue
        if a.get("provinz"):
            item["region"] = str(a["provinz"])
        out.append(item)
    return out


def _details(payload: dict) -> dict | None:
    """Prize classes: winners (all countries) and prize per winner."""
    try:
        rows = payload["auswertung"]["quoten"]["hauptlotterie"]["ziehungen"][0]["gewinnklassen"]
    except (KeyError, IndexError, TypeError):
        return None
    classes = []
    for r in rows:
        try:
            cls = {
                "cls": int(r["klasse"]),
                "tier": str(r.get("kurzbeschreibung", "")).replace(" ", ""),
                "winners": int(r.get("anzahl") or 0),
                "prize": float(r.get("quote") or 0.0),
            }
        except (KeyError, TypeError, ValueError):
            continue
        where = _where(r.get("aufteilung"))
        if where:                       # only the first three classes have it
            cls["where"] = where
        classes.append(cls)
    stake = None
    try:
        stake = float(payload["auswertung"]["spieleinsatz"]["hauptlotterie"])
    except (KeyError, TypeError, ValueError):
        pass
    return {"v": DETAILS_VERSION, "classes": classes, "stake_all": stake} if classes else None


def parse(payload: dict) -> dict | None:
    """Return {'date','main','euro','source','details'} or None when there is no draw on that day."""
    if not payload or payload.get("error") or "head" not in payload:
        return None
    try:
        rows = payload["zahlen"]["hauptlotterie"]["ziehungen"]
        main = [int(x) for x in rows[0]["zahlen"]]
        euro = [int(x) for x in rows[1]["zahlen"]]
        d = payload["head"]["datum"]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if len(main) != 5 or len(euro) != 2:
        return None
    return {"date": d, "main": sorted(main), "euro": sorted(euro), "source": "eurojackpot.com",
            "details": _details(payload)}


def fetch_day(d: date) -> dict | None:
    return parse(get_json(URL.format(d=d.isoformat()), REFERER))


def fetch_range(
    start: date,
    end: date,
    skip: set[str] | None = None,
    progress: Callable[[int, int], None] | None = None,
    workers: int = 4,
) -> list[dict]:
    skip = skip or set()
    days = [d for d in rules.candidate_dates(start, end) if d.isoformat() not in skip]
    if not days:
        return []
    fetch_day(days[-1])          # probe: fail immediately (not after 1000 retries) if blocked
    stop = threading.Event()

    def work(d: date):
        if stop.is_set():
            return None
        try:
            return fetch_day(d)
        except SourceError:
            stop.set()           # abort the remaining requests as soon as one fails
            raise

    out: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(work, days):
            done += 1
            if res:
                out.append(res)
            if progress:
                progress(done, len(days))
    return out


__all__ = ["parse", "fetch_day", "fetch_range", "SourceError"]
