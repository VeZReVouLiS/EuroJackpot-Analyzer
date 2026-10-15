from datetime import date

from app import rules
from app.db import Database
from app.sources import allwyn, importer, official


def test_official_parse_ok():
    payload = {
        "error": None,
        "head": {"datum": "2026-10-13"},
        "zahlen": {"hauptlotterie": {"ziehungen": [
            {"zahlen": ["35", "20", "22", "17", "11"]}, {"zahlen": ["4", "8"]}]}},
    }
    assert official.parse(payload) == {
        "date": "2026-10-13", "main": [11, 17, 20, 22, 35], "euro": [4, 8], "source": "eurojackpot.com"}


def test_official_parse_no_draw():
    assert official.parse({"error": "keine Daten"}) is None
    assert official.parse({}) is None


def test_allwyn_parse():
    draw = {"status": "results", "drawTime": 1791914400000,
            "winningNumbers": {"list": [35, 20, 22, 17, 11], "bonus": [8, 4]}}
    d = allwyn.parse(draw)
    assert d["date"] == "2026-10-13" and d["main"] == [11, 17, 20, 22, 35] and d["euro"] == [4, 8]
    assert allwyn.parse({"status": "active"}) is None


def test_candidate_dates():
    ds = list(rules.candidate_dates(date(2022, 3, 21), date(2022, 4, 5)))
    assert [d.isoformat() for d in ds] == ["2022-03-25", "2022-03-29", "2022-04-01", "2022-04-05"]
    assert list(rules.candidate_dates(date(2012, 1, 1), date(2012, 3, 22))) == []


def test_euro_max_eras():
    assert rules.euro_max(date(2012, 3, 23)) == 8
    assert rules.euro_max(date(2014, 10, 9)) == 8
    assert rules.euro_max(date(2014, 10, 10)) == 10
    assert rules.euro_max(date(2022, 3, 24)) == 10
    assert rules.euro_max(date(2022, 3, 25)) == 12


def test_import_csv_with_header_and_greek_dates():
    text = "Ημερομηνία;N1;N2;N3;N4;N5;E1;E2\n13/10/2026;35;20;22;17;11;4;8\n09/10/2026;1;2;3;4;5;6;7\n"
    out = importer.parse_text(text)
    assert [d["date"] for d in out] == ["2026-10-09", "2026-10-13"]
    assert out[1]["main"] == [11, 17, 20, 22, 35] and out[1]["euro"] == [4, 8]


def test_import_csv_no_header_single_cells():
    out = importer.parse_text("2026-10-13,11,17,20,22,35,4,8\n")
    assert out and out[0]["euro"] == [4, 8]


def test_import_json_objects_and_lists():
    text = '{"draws":[{"date":"2026-10-13","numbers":[11,17,20,22,35],"euroNumbers":[4,8]},' \
           '{"date":"09.10.2026","main":"1 2 3 4 5","euro":"6 7"}]}'
    out = importer.parse_text(text, "x.json")
    assert [d["date"] for d in out] == ["2026-10-09", "2026-10-13"]
    assert out[1]["main"] == [11, 17, 20, 22, 35] and out[1]["euro"] == [4, 8]
    assert out[0]["main"] == [1, 2, 3, 4, 5] and out[0]["euro"] == [6, 7]
    out2 = importer.parse_text('[["2026-10-13",11,17,20,22,35,4,8]]', "y.json")
    assert out2[0]["date"] == "2026-10-13"


def test_import_rejects_invalid_numbers():
    assert importer.parse_text("2026-10-13,11,17,20,22,99,4,8\n") == []


def test_db_roundtrip(tmp_path):
    db = Database(tmp_path / "t.db")
    d = {"date": "2026-10-13", "main": [35, 20, 22, 17, 11], "euro": [8, 4], "source": "t"}
    assert db.upsert_draws([d]) == 1
    db.upsert_draws([d])  # idempotent
    assert db.count() == 1 and db.last_date() == "2026-10-13"
    assert db.all_draws()[0]["main"] == [11, 17, 20, 22, 35]
    db.set_meta("k", "v")
    assert db.get_meta("k") == "v"
    db.close()
