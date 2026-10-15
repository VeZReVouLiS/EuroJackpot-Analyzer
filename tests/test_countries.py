import json

from app import countries
from app.api import Api
from app.db import Database
from app.paths import resource_dir


def test_catalogue_is_consistent():
    cat = countries.catalogue()
    assert set(cat["languages"]) == set(countries.LANGUAGES)
    ui = resource_dir() / "ui"
    for c in cat["countries"]:
        assert (ui / "flags" / f"{c['flag']}.svg").exists(), c["code"]
        if c["supported"]:
            assert c["local_lang"] in cat["languages"] and c["layout"] in ("allwyn", "official")
            assert c["price"] > 0 and c["tz"] and c["draw"]
        else:
            assert c["soon"]
    for lang in cat["languages"].values():
        assert (ui / "flags" / f"{lang['flag']}.svg").exists()
    assert {c["code"] for c in cat["countries"] if c["supported"]} == {"GR", "DE"}


def test_locales_have_the_same_keys():
    loc = resource_dir() / "locales"
    keys = {n: set(json.loads((loc / f"{n}.json").read_text(encoding="utf-8"))) for n in countries.LANGUAGES}
    assert keys["el"] == keys["en"] == keys["de"]


def test_price_per_country(tmp_path):
    assert countries.default_price("GR") == 2.5 and countries.default_price("DE") == 2.0
    assert countries.effective_price({"country": "DE", "prices": {"DE": 2.3}}) == 2.3
    assert countries.effective_price({"country": "DE", "prices": {"DE": 0}}) == 2.0
    api = Api(Database(tmp_path / "t.db"))
    api.set_setting("country", "DE")
    assert api.get_state()["price"] == 2.0
    api.set_setting("prices", {"DE": 2.25})
    assert api.get_state()["price"] == 2.25 and api.get_state()["default_price"] == 2.0
    assert api.get_locale("de")["nav.history"] == "Ziehungen"
