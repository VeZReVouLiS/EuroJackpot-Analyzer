"""Column generators. Every algorithm returns one column: 5 main (1-50) + 2 euro (1-12)."""
from __future__ import annotations

import random as _random
from typing import Callable

from . import rules

ALGOS = ["random", "hot", "cold", "overdue", "weighted", "balanced", "smart"]
AUTO_COLUMN = "auto_column"   # a random algorithm for every column
AUTO_TICKET = "auto_ticket"   # one random algorithm for the whole ticket


def _weights(block: list[dict], field: str, power: float, invert: bool = False, only_active=True) -> dict[int, float]:
    vals = {b["n"]: (b[field] or 0) for b in block if b["gap"] is not None or not only_active}
    if not vals:
        return {}
    hi = max(vals.values()) or 1
    out = {}
    for n, v in vals.items():
        x = (v / hi) if hi else 0
        if invert:
            x = 1 - x
        out[n] = (x + 0.05) ** power        # small floor: every number stays possible
    return out


def _pick(rng: _random.Random, weights: dict[int, float], k: int) -> list[int]:
    pool = dict(weights)
    chosen: list[int] = []
    for _ in range(k):
        total = sum(pool.values())
        r = rng.uniform(0, total)
        acc = 0.0
        pick = next(iter(pool))
        for n, w in pool.items():
            acc += w
            if r <= acc:
                pick = n
                break
        chosen.append(pick)
        del pool[pick]
    return sorted(chosen)


def _uniform(block_nums, rng, k):
    return sorted(rng.sample(list(block_nums), k))


def _euro_numbers(stats: dict, rng, algo: str) -> list[int]:
    block = [e for e in stats["euro"] if e["active"]]
    nums = [e["n"] for e in block]
    if algo in ("random", "smart"):
        return _uniform(nums, rng, rules.EURO_COUNT)
    if algo in ("hot", "weighted"):
        w = _weights(block, "pct", 3 if algo == "hot" else 1)
    elif algo == "cold":
        w = _weights(block, "pct", 3, invert=True)
    elif algo == "overdue":
        w = _weights(block, "gap", 3)
    else:  # balanced: one hot, one overdue
        a = _pick(rng, _weights(block, "pct", 2), 1)
        rest = {n: w for n, w in _weights(block, "gap", 2).items() if n not in a}
        return sorted(a + _pick(rng, rest, 1))
    return _pick(rng, w, rules.EURO_COUNT)


def _main_numbers(stats: dict, rng, algo: str) -> list[int]:
    block = stats["main"]
    nums = range(1, rules.MAIN_MAX + 1)
    if algo == "random":
        return _uniform(nums, rng, rules.MAIN_COUNT)
    if algo == "hot":
        return _pick(rng, _weights(block, "pct", 4), 5)
    if algo == "weighted":
        return _pick(rng, _weights(block, "pct", 1), 5)
    if algo == "cold":
        return _pick(rng, _weights(block, "pct", 4, invert=True), 5)
    if algo == "overdue":
        return _pick(rng, _weights(block, "gap", 3), 5)
    if algo == "balanced":
        hot = _pick(rng, _weights(block, "pct", 3), 2)
        over = {n: w for n, w in _weights(block, "gap", 3).items() if n not in hot}
        over_pick = _pick(rng, over, 1)
        taken = set(hot) | set(over_pick)
        rest = [n for n in nums if n not in taken]
        return sorted(hot + over_pick + rng.sample(rest, 2))
    # smart: random with "typical" shape (2-3 odd, 2-3 low, sum 90-160, no 4+ consecutive)
    for _ in range(5000):
        c = sorted(rng.sample(list(nums), 5))
        odd = sum(n % 2 for n in c)
        low = sum(n <= 25 for n in c)
        consec = sum(1 for a, b in zip(c, c[1:]) if b == a + 1)
        if 2 <= odd <= 3 and 2 <= low <= 3 and 90 <= sum(c) <= 160 and consec <= 1:
            return c
    return _uniform(nums, rng, 5)


def generate_column(stats: dict, algo: str, rng: _random.Random | None = None) -> dict:
    rng = rng or _random.SystemRandom()
    if algo not in ALGOS:
        raise ValueError(f"unknown algorithm: {algo}")
    return {"main": _main_numbers(stats, rng, algo), "euro": _euro_numbers(stats, rng, algo), "algo": algo}


def generate_ticket(
    stats: dict,
    columns: int,
    algo: str = AUTO_TICKET,
    rng: _random.Random | None = None,
    keep: list[dict] | None = None,
    price: float | None = None,
) -> dict:
    """keep: already locked columns (their position is preserved, the rest are regenerated).

    keep may contain None placeholders for slots to (re)generate.
    """
    if not 1 <= columns <= rules.MAX_COLUMNS:
        raise ValueError(f"columns must be 1..{rules.MAX_COLUMNS}")
    rng = rng or _random.SystemRandom()
    ticket_algo = algo
    if algo == AUTO_TICKET:
        ticket_algo = rng.choice(ALGOS)
    slots: list[dict | None] = list(keep or [])[:columns]
    slots += [None] * (columns - len(slots))
    seen = {(tuple(c["main"]), tuple(c["euro"])) for c in slots if c}
    for i, slot in enumerate(slots):
        if slot:
            continue
        for _ in range(50):
            a = rng.choice(ALGOS) if algo == AUTO_COLUMN else ticket_algo
            col = generate_column(stats, a, rng)
            key = (tuple(col["main"]), tuple(col["euro"]))
            if key not in seen:
                seen.add(key)
                break
        slots[i] = col
    price = rules.COLUMN_PRICE if price is None else float(price)
    return {
        "columns": slots,
        "algo": algo,
        "resolved_algo": ticket_algo if algo != AUTO_COLUMN else None,
        "price_per_column": price,
        "total": round(columns * price, 2),
    }
