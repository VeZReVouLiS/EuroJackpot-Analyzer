from datetime import date, datetime

import pytest

from app import evaluation, exporter, rules
from app.api import Api
from app.db import Database
from app.sources import importer

DRAW = {
    "date": "2026-10-13", "main": [11, 17, 20, 22, 35], "euro": [4, 8],
    "details": {"classes": [
        {"cls": 1, "tier": "5+2", "winners": 1, "prize": 120000000.0},
        {"cls": 4, "tier": "4+2", "winners": 169, "prize": 1780.0},
        {"cls": 5, "tier": "4+1", "winners": 3533, "prize": 106.4},
        {"cls": 9, "tier": "3+1", "winners": 73314, "prize": 14.6},
        {"cls": 13, "tier": "1+1", "winners": 69989, "prize": 2.5, "greek_only": True},
    ]},
}


def col(main, euro):
    return {"main": main, "euro": euro, "algo": "random"}


def test_column_tiers_and_prizes():
    ev = evaluation.evaluate_column
    jackpot = ev(col([11, 17, 20, 22, 35], [4, 8]), DRAW)
    assert jackpot["tier"] == "5+2" and jackpot["prize"] == 120000000.0 and jackpot["wins"]
    r = ev(col([11, 17, 20, 1, 2], [4, 9]), DRAW)
    assert r["tier"] == "3+1" and r["prize"] == 14.6 and r["main_hit"] == [11, 17, 20] and r["euro_hit"] == [4]
    assert ev(col([11, 1, 2, 3, 4], [4, 9]), DRAW)["prize"] == 2.5          # Greek add-on tier 1+1
    none = ev(col([1, 2, 3, 4, 5], [1, 2]), DRAW)
    assert none["tier"] == "0+0" and not none["wins"] and none["prize"] == 0
    assert not ev(col([11, 1, 2, 3, 4], [9, 10]), DRAW)["wins"]            # 1+0 pays nothing
    # tier exists in the format but this draw has no winner/prize listed -> no prize
    assert ev(col([11, 17, 1, 2, 3], [4, 8]), DRAW)["prize"] == 0.0


def test_unknown_prizes_without_details():
    d = {"date": "2020-01-03", "main": [1, 2, 3, 4, 5], "euro": [1, 2], "details": None}
    r = evaluation.evaluate_ticket([col([1, 2, 3, 9, 10], [1, 9])], d)
    assert not r["complete"] and r["columns"][0]["wins"] and r["columns"][0]["known"] is False


def test_ticket_total():
    r = evaluation.evaluate_ticket([col([11, 17, 20, 1, 2], [4, 9]), col([11, 1, 2, 3, 4], [4, 9]),
                                    col([1, 2, 3, 4, 5], [1, 2])], DRAW)
    assert r["total_prize"] == 17.1 and r["winning_columns"] == 2 and r["complete"]


def test_next_draw_dates():
    f = rules.next_draw_dates
    assert f(datetime(2026, 10, 14, 10, 0), 3) == [date(2026, 10, 16), date(2026, 10, 20), date(2026, 10, 23)]
    assert f(datetime(2026, 10, 13, 20, 0), 1) == [date(2026, 10, 13)]      # draw day, before the draw
    assert f(datetime(2026, 10, 13, 21, 30), 1) == [date(2026, 10, 16)]     # after the draw
    assert f(datetime(2021, 5, 3, 9, 0), 2) == [date(2021, 5, 7), date(2021, 5, 14)]   # Tuesdays did not exist


@pytest.fixture()
def api(tmp_path):
    db = Database(tmp_path / "t.db")
    db.upsert_draws([DRAW | {"source": "t"}])
    a = Api(db)
    # stats need history: add some filler draws
    import random
    rng = random.Random(3)
    filler = [{"date": f"2022-0{m}-{d:02d}", "main": sorted(rng.sample(range(1, 51), 5)),
               "euro": sorted(rng.sample(range(1, 11), 2)), "source": "t"} for m in range(4, 9) for d in (1, 8, 15, 22)]
    db.upsert_draws(filler)
    return a


def test_generate_saves_and_replaces_unplayed(api):
    t1 = api.generate(3, "random")
    assert t1["id"] and t1["target_date"] and not t1["played"] and t1["total"] == 7.5
    t2 = api.generate(4, "hot", [], "all", t1["id"])                 # same ticket id -> replaced
    assert t2["id"] == t1["id"] and len(api.get_tickets()["tickets"]) == 1
    assert len(api.get_tickets()["tickets"][0]["columns"]) == 4
    api.set_ticket_played(t2["id"], True)
    t3 = api.generate(2, "cold", [], "all", t2["id"])                # played -> never overwritten
    assert t3["id"] != t2["id"] and len(api.get_tickets()["tickets"]) == 2


def test_evaluation_totals_and_wins(api):
    db = api._db
    win = db.add_ticket("2026-10-12T10:00:00", "2026-10-13", "hot",
                        [col([11, 17, 20, 1, 2], [4, 9]), col([1, 2, 3, 4, 5], [1, 2])], 5.0)
    lose = db.add_ticket("2026-10-12T10:05:00", "2026-10-13", "cold", [col([1, 2, 3, 4, 5], [1, 2])], 2.5)
    future = db.add_ticket("2026-10-12T10:06:00", "2099-01-01", "random", [col([1, 2, 3, 4, 5], [1, 2])], 2.5)
    for tid in (win, lose, future):
        api.set_ticket_played(tid, True)
    r = api.evaluate_tickets()
    assert r["evaluated"] == 2 and r["wins"] == [{"id": win, "target_date": "2026-10-13", "total_prize": 14.6}]
    assert api.evaluate_tickets() == {"evaluated": 0, "wins": []}      # idempotent
    tot = api.get_tickets()
    assert tot["totals"]["spent"] == 10.0 and tot["totals"]["won"] == 14.6
    assert tot["totals"]["net"] == 14.6 - 7.5 and tot["totals"]["pending"] == 1 and tot["unseen_wins"] == 1
    api.mark_tickets_seen()
    assert api.get_tickets()["unseen_wins"] == 0


def test_unplayed_ticket_win_is_not_announced(api):
    tid = api._db.add_ticket("2026-10-12T10:00:00", "2026-10-13", "x", [col([11, 17, 20, 22, 35], [4, 8])], 2.5)
    assert api.evaluate_tickets()["wins"] == []                         # a suggestion, not a played ticket
    assert api._db.get_ticket(tid)["result"]["total_prize"] == 120000000.0
    assert api.get_tickets()["totals"]["won"] == 0                       # only played tickets count


def test_late_prize_table_completes_evaluation(api):
    db = api._db
    db.upsert_draws([{"date": "2026-10-16", "main": [1, 2, 3, 4, 5], "euro": [1, 2], "source": "t"}])
    tid = db.add_ticket("2026-10-14T10:00:00", "2026-10-16", "x", [col([1, 2, 3, 9, 10], [1, 9])], 2.5)
    api.set_ticket_played(tid, True)
    api.evaluate_tickets()
    assert db.get_ticket(tid)["result"]["complete"] is False
    db.upsert_draws([{"date": "2026-10-16", "main": [1, 2, 3, 4, 5], "euro": [1, 2], "source": "t",
                      "details": {"classes": [{"cls": 9, "tier": "3+1", "winners": 5, "prize": 20.0}]}}])
    api.evaluate_tickets()
    r = db.get_ticket(tid)["result"]
    assert r["complete"] and r["total_prize"] == 20.0


def test_ticket_history_export_import_roundtrip(api, tmp_path):
    tid = api._db.add_ticket("2026-10-12T10:00:00", "2026-10-13", "hot", [col([11, 17, 20, 1, 2], [4, 9])], 2.5)
    api.set_ticket_played(tid, True)
    api.evaluate_tickets()
    text = exporter.to_json(api._db.all_draws(with_details=True), api._db.all_tickets())
    db2 = Database(tmp_path / "other.db")
    assert importer.parse_tickets(text)[0]["target_date"] == "2026-10-13"
    assert db2.import_tickets(importer.parse_tickets(text)) == 1
    assert db2.import_tickets(importer.parse_tickets(text)) == 0       # no duplicates
    t = db2.all_tickets()[0]
    assert t["played"] and t["result"]["total_prize"] == 14.6
