"""Countries / languages catalogue (ui/countries.json, shared with the Home Assistant integration)."""
from __future__ import annotations

import json
from functools import lru_cache

from . import rules
from .paths import resource_dir

@lru_cache(maxsize=1)
def catalogue() -> dict:
    return json.loads((resource_dir() / "ui" / "countries.json").read_text(encoding="utf-8"))


def languages() -> tuple[str, ...]:
    """Every language of the app (one locale file each): the catalogue is the single list."""
    return tuple(catalogue()["languages"])


def get(code: str | None) -> dict | None:
    return next((c for c in catalogue()["countries"] if c["code"] == code and c.get("supported")), None)


def default_price(code: str | None) -> float:
    c = get(code)
    return float(c["price"]) if c else rules.COLUMN_PRICE


def effective_price(settings: dict) -> float:
    """The user's own price for the chosen country, else the country's default."""
    code = settings.get("country")
    custom = (settings.get("prices") or {}).get(code)
    try:
        if custom is not None and float(custom) > 0:
            return round(float(custom), 2)
    except (TypeError, ValueError):
        pass
    return default_price(code)
