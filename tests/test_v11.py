import io
import json
import sqlite3
import zipfile
from datetime import date

import pytest

from app import appupdate, exporter, updater
from app.db import Database
from app.sources import allwyn, importer, official
from app.sources.http import SourceError

OFFICIAL = {
    "error": None,
    "head": {"datum": "2026-10-13"},
    "zahlen": {"hauptlotterie": {"ziehungen": [{"zahlen": ["35", "20", "22", "17", "11"]}, {"zahlen": ["4", "8"]}]}},
    "auswertung": {
        "spieleinsatz": {"hauptlotterie": 75205218.0},
        "quoten": {"hauptlotterie": {"ziehungen": [{"gewinnklassen": [
            {"klasse": 1, "kurzbeschreibung": "5 + 2", "anzahl": 1, "quote": 120000000.0},
            {"klasse": 4, "kurzbeschreibung": "4 + 2", "anzahl": 169, "quote": 1780.0},
        ]}]}},
    },
}
ALLWYN = {
    "status": "results", "drawTime": 1791914400000, "drawId": 272,
    "winningNumbers": {"list": [35, 20, 22, 17, 11], "bonus": [4, 8]},
    "wagerStatistics": {"columns": 642038, "totalColumnsAll": 37602609.0, "totalSalesAll": 75205218},
    "prizeCategories": [
        {"id": 1, "divident": 120000000.0, "winners": 0, "winnersAll": 1},
        {"id": 4, "divident": 1780.0, "winners": 1, "winnersAll": 169},
        {"id": 13, "divident": 2.5, "winners": 69989, "gameType": "EJKAddon"},
    ],
}


def test_official_details():
    d = official.parse(OFFICIAL)
    cls = {c["tier"]: c for c in d["details"]["classes"]}
    assert cls["5+2"]["winners"] == 1 and cls["5+2"]["prize"] == 120000000.0
    assert cls["4+2"]["winners"] == 169 and d["details"]["stake_all"] == 75205218.0


def test_allwyn_details_and_merge():
    a = allwyn.parse(ALLWYN)
    cls = {c["tier"]: c for c in a["details"]["classes"]}
    assert cls["4+2"]["winners_gr"] == 1 and cls["4+2"]["winners"] == 169
    assert cls["1+1"]["greek_only"] and cls["1+1"]["winners"] == 69989
    m = allwyn.merge_details(official.parse(OFFICIAL)["details"], a["details"])
    by = {c["tier"]: c for c in m["classes"]}
    assert by["4+2"]["winners"] == 169 and by["4+2"]["winners_gr"] == 1
    assert by["5+2"]["winners_gr"] == 0 and "1+1" in by
    assert m["columns_gr"] == 642038 and m["draw_no"] == 272


def test_db_keeps_details_and_migrates(tmp_path):
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)      # v1.0 schema without details
    c.execute("CREATE TABLE draws(draw_date TEXT PRIMARY KEY,n1,n2,n3,n4,n5,e1,e2,source TEXT)")
    c.execute("INSERT INTO draws VALUES('2026-10-09',1,2,3,4,5,6,7,'x')")
    c.commit(); c.close()
    db = Database(p)
    assert db.dates_missing_details() == {"2026-10-09"}
    base = {"date": "2026-10-09", "main": [1, 2, 3, 4, 5], "euro": [6, 7], "source": "a"}
    db.upsert_draws([{**base, "details": {"classes": [{"tier": "5+2"}]}}])
    db.upsert_draws([base])            # a later import without details must not erase them
    assert db.get_draw("2026-10-09")["details"]["classes"][0]["tier"] == "5+2"
    assert db.dates_missing_details() == set()


def test_export_import_roundtrip(tmp_path):
    db = Database(tmp_path / "a.db")
    d = official.parse(OFFICIAL)
    db.upsert_draws([d])
    text = exporter.to_json(db.all_draws(with_details=True))
    out = importer.parse_text(text, "x.json")
    assert out[0]["details"]["classes"][0]["tier"] == "5+2" and out[0]["main"] == [11, 17, 20, 22, 35]
    db2 = Database(tmp_path / "b.db")
    db2.upsert_draws(out)
    assert db2.get_draw("2026-10-13")["details"]["stake_all"] == 75205218.0
    csv_text = exporter.to_csv(db.all_draws())
    assert importer.parse_text(csv_text, "x.csv")[0]["euro"] == [4, 8]


def test_version_compare():
    assert appupdate.is_newer("v1.2.0", "1.1.0") and appupdate.is_newer("1.10.0", "1.9.9")
    assert not appupdate.is_newer("v1.1.0", "1.1.0") and not appupdate.is_newer("1.0.9", "1.1.0")


def test_pick_assets_only_accepts_own_repo(monkeypatch):
    monkeypatch.setattr(appupdate.version, "RELEASE_ASSET", "EuroJackpotApp-portable-win.zip")
    rel = {"assets": [
        {"name": "EuroJackpotApp-portable-win.zip", "browser_download_url": "https://github.com/me/app/releases/download/v1/EuroJackpotApp-portable-win.zip"},
        {"name": "EuroJackpotApp-portable-win.zip.sha256", "browser_download_url": "https://evil.example.com/x.sha256"},
    ]}
    z, s = appupdate.pick_assets(rel, "me/app")
    assert z and s is None


def test_sha_and_zip_slip(tmp_path):
    h = "a" * 64
    assert appupdate.expected_sha256(f"{h}  EuroJackpotApp-portable-win.zip") == h
    with pytest.raises(appupdate.AppUpdateError):
        appupdate.expected_sha256("garbage")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("../evil.txt", "x")
    with pytest.raises(appupdate.AppUpdateError):
        appupdate.safe_extract(bad, tmp_path / "out")
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as z:
        z.writestr("EuroJackpotApp/EuroJackpotApp.exe", "MZ")
    assert appupdate.safe_extract(good, tmp_path / "ok").name == "EuroJackpotApp"


def test_check_not_configured_and_errors(monkeypatch):
    assert appupdate.check("")["configured"] is False
    def boom(*a, **k): raise OSError("offline")
    monkeypatch.setattr(appupdate, "_open", boom)
    r = appupdate.check("me/app")
    assert r["error"] and not r["newer"]


def test_update_error_reports_both_sources(tmp_path, monkeypatch):
    db = Database(tmp_path / "e.db")
    def f1(*a, **k): raise SourceError("HTTP 403 Forbidden")
    def f2(*a, **k): raise SourceError("HTTP 403 Forbidden (allwyn)")
    monkeypatch.setattr(official, "fetch_range", f1)
    monkeypatch.setattr(allwyn, "fetch_range", f2)
    with pytest.raises(updater.UpdateError) as ei:
        updater.update(db, today=date(2026, 10, 15))
    assert set(ei.value.errors) == {"eurojackpot.com", "allwyn.gr"} and "403" in str(ei.value)


def test_update_falls_back_to_allwyn(tmp_path, monkeypatch):
    db = Database(tmp_path / "f.db")
    monkeypatch.setattr(official, "fetch_range", lambda *a, **k: (_ for _ in ()).throw(SourceError("x")))
    monkeypatch.setattr(allwyn, "fetch_range", lambda *a, **k: [allwyn.parse(ALLWYN)])
    r = updater.update(db, today=date(2026, 10, 15))
    assert r["source"] == "allwyn.gr" and db.count() == 1


def test_official_probe_fails_fast(monkeypatch):
    calls = []
    def bad(d): calls.append(d); raise SourceError("HTTP 403")
    monkeypatch.setattr(official, "fetch_day", bad)
    with pytest.raises(SourceError):
        official.fetch_range(date(2024, 1, 1), date(2026, 10, 15))
    assert len(calls) == 1          # the probe only; no thousand retries
