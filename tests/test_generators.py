import random

import pytest

from app import generators, stats


def D(date, main, euro):
    return {"date": date, "main": main, "euro": euro, "source": "t"}


@pytest.fixture(scope="module")
def st():
    rng = random.Random(1)
    draws = []
    from datetime import date, timedelta
    d = date(2022, 4, 1)
    for _ in range(120):
        draws.append(D(d.isoformat(), sorted(rng.sample(range(1, 51), 5)), sorted(rng.sample(range(1, 13), 2))))
        d += timedelta(days=3)
    return stats.compute(draws)


@pytest.mark.parametrize("algo", generators.ALGOS)
def test_each_algo_valid_column(st, algo):
    rng = random.Random(7)
    for _ in range(100):
        c = generators.generate_column(st, algo, rng)
        assert len(set(c["main"])) == 5 and all(1 <= n <= 50 for n in c["main"])
        assert len(set(c["euro"])) == 2 and all(1 <= n <= 12 for n in c["euro"])
        assert c["main"] == sorted(c["main"]) and c["algo"] == algo


def test_hot_prefers_frequent_numbers(st):
    rng = random.Random(3)
    top = set(st["ranking"]["main"]["hot"])
    hits = sum(len(top & set(generators.generate_column(st, "hot", rng)["main"])) for _ in range(300))
    rnd = sum(len(top & set(generators.generate_column(st, "random", rng)["main"])) for _ in range(300))
    assert hits > rnd


@pytest.mark.parametrize("n", [1, 5, 12])
def test_ticket_cost_and_size(st, n):
    t = generators.generate_ticket(st, n, "random", random.Random(2))
    assert len(t["columns"]) == n and t["total"] == n * 2.5 and t["price_per_column"] == 2.5
    assert len({(tuple(c["main"]), tuple(c["euro"])) for c in t["columns"]}) == n


def test_ticket_bounds(st):
    for bad in (0, 13):
        with pytest.raises(ValueError):
            generators.generate_ticket(st, bad)


def test_auto_column_mixes_algos(st):
    t = generators.generate_ticket(st, 12, generators.AUTO_COLUMN, random.Random(5))
    assert len({c["algo"] for c in t["columns"]}) > 1 and t["resolved_algo"] is None


def test_auto_ticket_single_algo(st):
    t = generators.generate_ticket(st, 8, generators.AUTO_TICKET, random.Random(5))
    assert len({c["algo"] for c in t["columns"]}) == 1 and t["resolved_algo"] in generators.ALGOS


def test_locked_columns_preserved(st):
    first = generators.generate_ticket(st, 4, "hot", random.Random(1))
    keep = [first["columns"][0], None, first["columns"][2], None]
    t = generators.generate_ticket(st, 4, "cold", random.Random(9), keep=keep)
    assert t["columns"][0] == first["columns"][0] and t["columns"][2] == first["columns"][2]
    assert t["columns"][1]["algo"] == "cold"
