import json
import time
import urllib.error
import urllib.request

import pytest

from app.api import Api
from app.db import Database
from app.server import AppServer


@pytest.fixture()
def srv(tmp_path):
    db = Database(tmp_path / "s.db")
    s = AppServer(Api(db))
    s.start()
    yield s
    s.stop()
    db.close()


def rpc(srv, name, args=(), token="__good__", host=None):
    h = {"X-Token": srv.token if token == "__good__" else token}
    if host:
        h["Host"] = host
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/rpc", data=json.dumps({"name": name, "args": list(args)}).encode(), headers=h)
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def status(fn):
    try:
        return fn().status
    except urllib.error.HTTPError as e:
        return e.code


def test_rpc_requires_token(srv):
    assert rpc(srv, "get_state")["result"]["version"]
    with pytest.raises(urllib.error.HTTPError) as e:
        rpc(srv, "get_state", token="wrong")
    assert e.value.code == 403
    with pytest.raises(urllib.error.HTTPError):
        rpc(srv, "get_state", token="")


def test_rpc_rejects_foreign_host_and_private_methods(srv):
    with pytest.raises(urllib.error.HTTPError) as e:
        rpc(srv, "get_state", host="evil.example.com")      # DNS rebinding
    assert e.value.code == 403
    assert "error" in rpc(srv, "_bind", [None])              # private methods are not callable


def test_ping_and_close_detection(srv):
    assert not srv.pinged
    req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/ping", headers={"X-Token": srv.token})
    assert json.loads(urllib.request.urlopen(req, timeout=5).read())["ok"]
    assert srv.pinged
    t = time.time()
    srv.wait_until_window_closed(idle_timeout=1.5)           # no more pings -> returns
    assert time.time() - t < 6


def test_index_served_with_token_url(srv):
    assert "?t=" in srv.url
    body = urllib.request.urlopen(f"http://127.0.0.1:{srv.port}/index.html", timeout=5).read().decode("utf-8")
    assert "EuroJackpot Analyzer" in body
