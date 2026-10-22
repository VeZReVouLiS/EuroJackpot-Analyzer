"""Ticket sync through the hidden app data folder of the user's own Google Drive.

The app only asks for the scope `drive.appdata`: it can see and change the one file it created itself (in a folder that is
not shown in Drive), never the other files of the user. The sign-in is the standard "installed app" OAuth flow with PKCE:
the system browser opens Google's page, Google calls back a tiny web server that listens on 127.0.0.1 for a moment,
and the tokens stay on this device. Nothing passes through a server of ours.

The class `Drive` has the same two calls as `ticket_sync.Gist` (pull_or_create / push), so the sync code does not care.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import google_client, tls
from .ticket_sync import FILE, SyncError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.appdata"
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"

DONE_PAGE = ("<!doctype html><meta charset='utf-8'><title>EuroJackpot Analyzer</title>"
             "<body style='font:18px system-ui;text-align:center;margin-top:20vh;color:#222'>"
             "<h2>{title}</h2><p>{text}</p></body>")


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def auth_url(redirect_uri: str, challenge: str, state: str, client_id: str | None = None) -> str:
    q = {"client_id": client_id or google_client.CLIENT_ID, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPE,
         "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
         "access_type": "offline", "prompt": "consent"}        # offline + consent: Google then always returns a refresh token
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def _post_form(url: str, form: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=tls.context()) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error_description") or ""
        except Exception:
            detail = ""
        raise SyncError(f"Google sign-in failed ({e.code}) {detail}".strip()) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SyncError(f"No connection to Google: {getattr(e, 'reason', e)}") from e


def _tokens(resp: dict, old_refresh: str = "") -> dict:
    return {"access_token": resp["access_token"], "refresh_token": resp.get("refresh_token") or old_refresh,
            "expires_at": int(time.time()) + int(resp.get("expires_in", 3600)) - 60}


def exchange_code(code: str, verifier: str, redirect_uri: str) -> dict:
    resp = _post_form(TOKEN_URL, {"code": code, "client_id": google_client.CLIENT_ID, "client_secret": google_client.client_secret(),
                                  "code_verifier": verifier, "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    t = _tokens(resp)
    if not t["refresh_token"]:
        raise SyncError("Google did not return a refresh token. Remove the app at myaccount.google.com/permissions and try again.")
    return t


def refresh(tokens: dict) -> dict:
    resp = _post_form(TOKEN_URL, {"refresh_token": tokens["refresh_token"], "client_id": google_client.CLIENT_ID,
                                  "client_secret": google_client.client_secret(), "grant_type": "refresh_token"})
    return _tokens(resp, tokens["refresh_token"])


class LoopbackFlow:
    """One sign-in: a one-shot web server on 127.0.0.1 that receives Google's redirect."""

    def __init__(self, texts: dict | None = None):
        self.verifier, challenge = pkce_pair()
        self.state = secrets.token_urlsafe(16)
        self.result: dict = {}
        self.event = threading.Event()
        flow = self
        t = texts or {"title": "Done", "text": "You can close this tab and go back to EuroJackpot Analyzer."}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "code" not in q and "error" not in q:       # favicon and the like
                    self.send_response(204)
                    self.end_headers()
                    return
                ok = q.get("state", [""])[0] == flow.state and "code" in q
                flow.result = {"code": q["code"][0]} if ok else {"error": q.get("error", ["state mismatch"])[0]}
                body = DONE_PAGE.format(title=t["title"] if ok else "Error", text=t["text"] if ok else flow.result["error"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                flow.event.set()

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.redirect_uri = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.url = auth_url(self.redirect_uri, challenge, self.state)

    def wait(self, timeout: float = 300) -> dict:
        """Block until Google calls back (or the timeout), return the tokens."""
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        try:
            if not self.event.wait(timeout):
                raise SyncError("The Google sign-in was not completed in time.")
            if "error" in self.result:
                raise SyncError(f"Google sign-in was cancelled or refused ({self.result['error']}).")
            return exchange_code(self.result["code"], self.verifier, self.redirect_uri)
        finally:
            self.httpd.shutdown()
            self.httpd.server_close()


class Drive:
    """Same interface as ticket_sync.Gist: pull_or_create() and push(doc); `id` is the id of the file."""

    def __init__(self, tokens: dict, file_id: str | None = None, on_tokens=None):
        self.tokens, self.id, self.on_tokens = dict(tokens), file_id or None, on_tokens

    def _token(self) -> str:
        if int(time.time()) >= int(self.tokens.get("expires_at", 0)):
            self.tokens = refresh(self.tokens)
            if self.on_tokens:
                self.on_tokens(self.tokens)
        return self.tokens["access_token"]

    def _call(self, method: str, url: str, body: bytes | None = None, content_type: str | None = None, raw: bool = False):
        headers = {"Authorization": f"Bearer {self._token()}", "User-Agent": "EuroJackpotAnalyzer"}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30, context=tls.context()) as r:
                data = r.read().decode("utf-8")
                return data if raw else (json.loads(data) if data.strip() else None)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SyncError(f"Google Drive refused the request ({e.code}). Sign in with Google again.") from e
            if e.code == 404 and self.id:
                raise SyncError("The sync file was not found in Google Drive. Disconnect and connect again.") from e
            raise SyncError(f"Google Drive error {e.code} {e.reason}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SyncError(f"No connection to Google Drive: {getattr(e, 'reason', e)}") from e

    def _find(self) -> str | None:
        q = urllib.parse.urlencode({"spaces": "appDataFolder", "q": f"name = '{FILE}' and trashed = false",
                                    "fields": "files(id,modifiedTime)", "orderBy": "modifiedTime desc", "pageSize": "5"})
        files = (self._call("GET", f"{API}/files?{q}") or {}).get("files") or []
        return files[0]["id"] if files else None

    def pull_or_create(self) -> dict | None:
        if not self.id:
            self.id = self._find()
        if not self.id:
            self.id = self._create({"format": "eurojackpot-analyzer-tickets", "version": 1, "tickets": [], "tombstones": {}})
            return None
        text = self._call("GET", f"{API}/files/{self.id}?alt=media", raw=True)
        try:
            return json.loads(text) if text and text.strip() else None
        except ValueError as e:
            raise SyncError("The sync file is damaged.") from e

    def _create(self, doc: dict) -> str:
        boundary = "ejb" + secrets.token_hex(8)
        meta = json.dumps({"name": FILE, "parents": ["appDataFolder"], "mimeType": "application/json"})
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{json.dumps(doc, ensure_ascii=False)}\r\n--{boundary}--").encode("utf-8")
        res = self._call("POST", f"{UPLOAD}/files?uploadType=multipart&fields=id", body, f"multipart/related; boundary={boundary}")
        return res["id"]

    def push(self, doc: dict) -> None:
        self._call("PATCH", f"{UPLOAD}/files/{self.id}?uploadType=media", json.dumps(doc, ensure_ascii=False).encode("utf-8"),
                   "application/json")
