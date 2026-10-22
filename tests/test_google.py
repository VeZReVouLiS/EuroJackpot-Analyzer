"""Ticket sync through Google Drive (app data folder): PKCE, the loopback sign-in, the Drive calls, the Api wiring. No network."""
import base64
import hashlib
import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from app import google_client, google_drive, ticket_sync
from app.api import Api
from app.db import Database


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(routes, calls):
    """routes: list of (method, url fragment, status, payload); the first match is used (and consumed)."""
    def opener(req, timeout=0, context=None):
        calls.append((req.get_method(), req.full_url, req.data, dict(req.header_items())))
        for i, (method, frag, status, payload) in enumerate(routes):
            if req.get_method() == method and frag in req.full_url:
                routes.pop(i)
                if status >= 400:
                    raise urllib.error.HTTPError(req.full_url, status, "err", {}, io.BytesIO(b"{}"))
                body = payload if isinstance(payload, str) else json.dumps(payload)
                return FakeResponse(body.encode("utf-8"))
        raise AssertionError(f"unexpected call {req.get_method()} {req.full_url}")
    return opener


TOK = {"access_token": "at", "refresh_token": "rt", "expires_at": int(time.time()) + 3000}
DOC = ticket_sync.to_doc([{"uid": "u1", "created_at": "2026-10-20T10:00:00", "target_date": "2026-10-23", "algo": "manual", "columns": [],
                           "price": 2.5, "played": False, "updated_at": "2026-10-20T10:00:00.000Z"}], {})


def test_pkce_and_auth_url():
    verifier, challenge = google_drive.pkce_pair()
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert len(verifier) >= 43 and "=" not in challenge
    url = google_drive.auth_url("http://127.0.0.1:5555", challenge, "st")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["scope"] == ["https://www.googleapis.com/auth/drive.appdata"]          # only the hidden app data folder
    assert q["code_challenge_method"] == ["S256"] and q["access_type"] == ["offline"] and q["state"] == ["st"]
    assert q["client_id"] == [google_client.CLIENT_ID] and q["redirect_uri"] == ["http://127.0.0.1:5555"]


def test_loopback_flow_receives_the_code(monkeypatch):
    got = {}
    monkeypatch.setattr(google_drive, "exchange_code", lambda code, verifier, redirect: got.update(code=code, redirect=redirect) or dict(TOK))
    flow = google_drive.LoopbackFlow()
    state = flow.state

    def browser():
        time.sleep(0.2)
        urllib.request.urlopen(f"{flow.redirect_uri}/?code=abc&state={state}", timeout=5).read()

    threading.Thread(target=browser).start()
    assert flow.wait(10)["refresh_token"] == "rt" and got["code"] == "abc" and got["redirect"] == flow.redirect_uri


def test_loopback_flow_rejects_a_wrong_state_and_errors(monkeypatch):
    monkeypatch.setattr(google_drive, "exchange_code", lambda *a: pytest.fail("must not exchange"))
    for query in ("code=abc&state=WRONG", "error=access_denied&state=x"):
        flow = google_drive.LoopbackFlow()
        threading.Thread(target=lambda: (time.sleep(0.2), urllib.request.urlopen(f"{flow.redirect_uri}/?{query}", timeout=5).read())).start()
        with pytest.raises(ticket_sync.SyncError):
            flow.wait(10)


def test_exchange_needs_a_refresh_token(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen([("POST", "oauth2.googleapis.com/token", 200, {"access_token": "a", "expires_in": 3600})], calls))
    monkeypatch.setattr(google_client, "client_secret", lambda: "s")
    with pytest.raises(ticket_sync.SyncError, match="refresh token"):
        google_drive.exchange_code("c", "v", "http://127.0.0.1:1")
    assert b"code_verifier=v" in calls[0][2] and b"client_secret=s" in calls[0][2]


def test_drive_creates_then_updates(monkeypatch):
    calls = []
    routes = [("GET", "/files?", 200, {"files": []}), ("POST", "uploadType=multipart", 200, {"id": "F1"}), ("PATCH", "/files/F1", 200, {})]
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen(routes, calls))
    d = google_drive.Drive(dict(TOK))
    assert d.pull_or_create() is None and d.id == "F1"
    assert "spaces=appDataFolder" in calls[0][1] and "eurojackpot-tickets.json" in urllib.parse.unquote(calls[0][1])
    assert b'"parents": ["appDataFolder"]' in calls[1][2] and calls[0][3]["Authorization"] == "Bearer at"
    d.push(DOC)
    assert json.loads(calls[2][2])["tickets"][0]["uid"] == "u1"


def test_drive_finds_and_reads_an_existing_file(monkeypatch):
    calls = []
    routes = [("GET", "/files?", 200, {"files": [{"id": "F9"}]}), ("GET", "/files/F9?alt=media", 200, json.dumps(DOC))]
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen(routes, calls))
    assert google_drive.Drive(dict(TOK)).pull_or_create()["tickets"][0]["uid"] == "u1"
    calls.clear()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen([("GET", "/files/F9?alt=media", 200, json.dumps(DOC))], calls))
    assert google_drive.Drive(dict(TOK), "F9").pull_or_create()["format"] == "eurojackpot-analyzer-tickets"      # known id: no search


def test_drive_refreshes_an_expired_token(monkeypatch):
    saved = []
    monkeypatch.setattr(google_drive, "refresh", lambda t: {**t, "access_token": "new", "expires_at": int(time.time()) + 3000})
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen([("GET", "/files/F1?alt=media", 200, json.dumps(DOC))], calls))
    d = google_drive.Drive({**TOK, "expires_at": 1}, "F1", on_tokens=saved.append)
    d.pull_or_create()
    assert calls[0][3]["Authorization"] == "Bearer new" and saved[0]["access_token"] == "new"


def test_drive_errors_are_readable(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen([("GET", "/files", 401, {})], []))
    with pytest.raises(ticket_sync.SyncError, match="Sign in with Google again"):
        google_drive.Drive(dict(TOK)).pull_or_create()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen([("GET", "/files/F1", 404, {})], []))
    with pytest.raises(ticket_sync.SyncError, match="not found"):
        google_drive.Drive(dict(TOK), "F1").pull_or_create()


class FakeDrive:
    instances = []

    def __init__(self, tokens, file_id=None, on_tokens=None):
        self.tokens, self.id, FakeDrive.pushed = tokens, file_id or None, []
        FakeDrive.instances.append(self)

    def pull_or_create(self):
        self.id = self.id or "FILE1"
        return DOC

    def push(self, doc):
        FakeDrive.pushed.append(doc)


def test_api_syncs_through_google_drive(tmp_path, monkeypatch):
    monkeypatch.setattr(google_drive, "Drive", FakeDrive)
    api = Api(Database(tmp_path / "t.db"))
    assert api.sync_status()["connected"] is False and api.sync_status()["provider"] == "github"
    api.set_setting("sync_provider", "google")
    api.set_setting("google_tokens", dict(TOK))
    st = api.sync_status()
    assert st["connected"] is True and st["provider"] == "google" and api.get_state()["sync"] is True
    res = api.sync_now()
    assert res["added"] == 1 and res["tickets"] == 1
    assert api.get_settings()["sync_file"] == "FILE1" and api.get_settings()["sync_gist"] == ""
    api.sync_disconnect()
    st = api.sync_status()
    assert st["connected"] is False and api.get_settings()["google_tokens"] == {} and api.get_settings()["sync_file"] == ""


def test_github_still_works_and_is_the_default(tmp_path, monkeypatch):
    calls = []

    class FakeGist:
        def __init__(self, token, gist_id=None):
            calls.append(token)
            self.id = gist_id or "G1"

        def pull_or_create(self):
            return None

        def push(self, doc):
            pass

    monkeypatch.setattr(ticket_sync, "Gist", FakeGist)
    api = Api(Database(tmp_path / "t.db"))
    api.sync_connect("tok")
    assert calls == ["tok"] and api.sync_status()["provider"] == "github" and api.get_settings()["sync_gist"] == "G1"


def test_google_connect_needs_the_secret(tmp_path, monkeypatch):
    monkeypatch.setattr(google_client, "client_secret", lambda: "")
    api = Api(Database(tmp_path / "t.db"))
    assert api.sync_status()["google_available"] is False
    with pytest.raises(ValueError):
        api.google_connect_start()


def test_a_failed_google_sign_in_keeps_github(tmp_path, monkeypatch):
    class FailingFlow:
        url = "https://accounts.example/auth"

        def __init__(self, texts=None):
            pass

        def wait(self, timeout=0):
            raise ticket_sync.SyncError("cancelled")

    monkeypatch.setattr(google_client, "client_secret", lambda: "s")
    monkeypatch.setattr(google_drive, "LoopbackFlow", FailingFlow)
    monkeypatch.setattr("app.api.webbrowser.open", lambda url: True)
    api = Api(Database(tmp_path / "t.db"))
    api.set_setting("sync_token", "ghp_x")
    api.set_setting("sync_gist", "G1")
    assert api.sync_status()["connected"] is True
    api.google_connect_start()
    for _ in range(100):
        if api.google_connect_status()["state"] != "waiting":
            break
        time.sleep(0.05)
    assert api.google_connect_status()["state"] == "error"
    st = api.sync_status()
    assert st["provider"] == "github" and st["connected"] is True and api.get_settings()["sync_token"] == "ghp_x"


def test_a_failed_sync_after_google_sign_in_keeps_github(tmp_path, monkeypatch):
    class OkFlow:
        url = "https://accounts.example/auth"

        def __init__(self, texts=None):
            pass

        def wait(self, timeout=0):
            return dict(TOK)

    class BrokenDrive(FakeDrive):
        def pull_or_create(self):
            raise ticket_sync.SyncError("Drive API is not enabled")

    monkeypatch.setattr(google_client, "client_secret", lambda: "s")
    monkeypatch.setattr(google_drive, "LoopbackFlow", OkFlow)
    monkeypatch.setattr(google_drive, "Drive", BrokenDrive)
    monkeypatch.setattr("app.api.webbrowser.open", lambda url: True)
    api = Api(Database(tmp_path / "t.db"))
    api.set_setting("sync_token", "ghp_x")
    api.google_connect_start()
    for _ in range(100):
        if api.google_connect_status()["state"] != "waiting":
            break
        time.sleep(0.05)
    assert api.google_connect_status()["state"] == "error" and "not enabled" in api.google_connect_status()["error"]
    s = api.get_settings()
    assert s["sync_provider"] == "github" and s["sync_token"] == "ghp_x" and s["google_tokens"] == {}


def test_disconnect_only_the_provider_in_use(tmp_path):
    api = Api(Database(tmp_path / "t.db"))
    api.set_setting("sync_token", "ghp_x")
    api.set_setting("google_tokens", dict(TOK))
    api.set_setting("sync_provider", "google")
    api.sync_disconnect()
    s = api.get_settings()
    assert s["google_tokens"] == {} and s["sync_token"] == "ghp_x"          # the GitHub token is still there
    api.set_setting("sync_provider", "github")
    api.sync_disconnect()
    assert api.get_settings()["sync_token"] == ""


def test_github_connection_is_found_again_after_an_unfinished_google_sign_in(tmp_path):
    api = Api(Database(tmp_path / "t.db"))
    api.set_setting("sync_token", "ghp_x")
    api.set_setting("sync_provider", "google")          # the state an older version could leave behind
    st = api.sync_status()
    assert st["provider"] == "github" and st["connected"] is True


def test_the_page_left_in_the_browser_speaks_the_app_language(monkeypatch):
    monkeypatch.setattr(google_drive, "exchange_code", lambda *a: dict(TOK))
    flow = google_drive.LoopbackFlow({"title": "Συνδεδεμένο με το Google Drive", "text": "Μπορείς να κλείσεις αυτό το παράθυρο"})
    page = {}

    def browser():
        time.sleep(0.2)
        page["html"] = urllib.request.urlopen(f"{flow.redirect_uri}/?code=abc&state={flow.state}", timeout=5).read().decode("utf-8")

    t = threading.Thread(target=browser)
    t.start()
    flow.wait(10)
    t.join()
    assert "Συνδεδεμένο με το Google Drive" in page["html"] and "Μπορείς να κλείσεις" in page["html"] and "window.close()" in page["html"]
