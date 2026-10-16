import json
from pathlib import Path

import pytest

from app import ticket_sync
from app.api import Api
from app.db import Database

C1 = [{"main": [1, 2, 3, 4, 5], "euro": [1, 2], "algo": "manual"}]
C2 = [{"main": [7, 14, 21, 28, 35], "euro": [3, 9], "algo": "hot"}]


def t(uid, at, played=False, cols=C1, target="2026-10-20"):
    return {"uid": uid, "created_at": "2026-10-16T10:00:00", "target_date": target, "algo": "manual", "columns": cols, "price": 2.5,
            "played": played, "updated_at": at}


def test_merge_last_change_wins_and_keeps_both_sides():
    local = [t("a", "2026-10-16T12:00:00Z", played=True), t("b", "2026-10-16T09:00:00Z")]
    remote = ticket_sync.to_doc([t("a", "2026-10-16T11:00:00Z", played=False), t("c", "2026-10-16T08:00:00Z")], {})
    merged, tombs = ticket_sync.merge(local, remote, {})
    by = {m["uid"]: m for m in merged}
    assert set(by) == {"a", "b", "c"} and by["a"]["played"] is True and tombs == {}


def test_merge_deletions_win_only_over_older_versions():
    local = [t("a", "2026-10-16T09:00:00Z"), t("b", "2026-10-16T13:00:00Z")]
    remote = ticket_sync.to_doc([], {"a": "2026-10-16T10:00:00Z", "b": "2026-10-16T10:00:00Z"})
    merged, tombs = ticket_sync.merge(local, remote, {"c": "x"})
    assert [m["uid"] for m in merged] == ["b"]           # a was deleted after its last change, b was changed after the deletion
    assert set(tombs) == {"a", "b", "c"}


def test_two_devices_converge(tmp_path, monkeypatch):
    """Two apps syncing through a fake gist end up with the same tickets, deletions included."""
    store = {"doc": None}

    class FakeGist:
        def __init__(self, token, gist_id=None):
            self.id = gist_id or "g1"

        def pull_or_create(self):
            return store["doc"]

        def push(self, doc):
            store["doc"] = json.loads(json.dumps(doc))

    monkeypatch.setattr(ticket_sync, "Gist", FakeGist)
    a, b = Api(Database(tmp_path / "a.db")), Api(Database(tmp_path / "b.db"))
    for x in (a, b):
        x.set_setting("sync_token", "tok")
    ta = a.save_manual_ticket(C1, "2026-10-20")
    a.sync_now()
    r = b.sync_now()
    assert r["added"] == 1 and len(b._db.all_tickets()) == 1
    tb = b._db.all_tickets()[0]
    assert tb["uid"] == ta["uid"] and tb["columns"][0]["main"] == [1, 2, 3, 4, 5]
    b.set_ticket_played(tb["id"], True)
    b.sync_now()
    a.sync_now()
    assert a._db.all_tickets()[0]["played"] is True
    a.delete_ticket(a._db.all_tickets()[0]["id"])
    a.sync_now()
    b.sync_now()
    assert b._db.all_tickets() == []
    assert a.sync_now()["tickets"] == 0
