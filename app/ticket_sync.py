"""Ticket sync between devices through a private GitHub gist of the user.

Every device keeps its own tickets and merges them with the gist ("last change wins" per ticket, deletions are remembered
as tombstones). The merge is a pure function (also used by the Home Assistant integration and ported to JavaScript for the
web / Android app, with a parity test); the HTTP part is a thin client.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import tls

FILE = "eurojackpot-tickets.json"
DESCRIPTION = "EuroJackpot Analyzer tickets (synced)"
API = "https://api.github.com"
FIELDS = ("uid", "created_at", "target_date", "algo", "columns", "price", "played", "updated_at")


class SyncError(Exception):
    """Sync failed; the message is safe to show."""


def uid_of(t: dict) -> str:
    return t.get("uid") or f"{t['created_at']}|{t['target_date']}"


def sync_view(t: dict) -> dict:
    """The part of a ticket that travels between devices."""
    out = {k: t.get(k) for k in FIELDS}
    out["uid"] = uid_of(t)
    out["updated_at"] = t.get("updated_at") or t["created_at"]
    out["played"] = bool(t.get("played"))
    return out


def merge(local: list[dict], remote: dict | None, local_tombstones: dict[str, str] | None = None) -> tuple[list[dict], dict[str, str]]:
    """Merge local tickets (sync views) with the remote document. Returns (tickets sorted by uid, tombstones)."""
    remote = remote or {}
    tombs: dict[str, str] = dict(remote.get("tombstones") or {})
    for uid, at in (local_tombstones or {}).items():
        if at > tombs.get(uid, ""):
            tombs[uid] = at
    best: dict[str, dict] = {}
    for t in list(remote.get("tickets") or []) + [sync_view(x) for x in local]:
        u = sync_view(t)
        cur = best.get(u["uid"])
        if cur is None or u["updated_at"] > cur["updated_at"]:
            best[u["uid"]] = u
    merged = [t for uid, t in best.items() if tombs.get(uid, "") < t["updated_at"]]
    return sorted(merged, key=lambda t: t["uid"]), tombs


def to_doc(tickets: list[dict], tombstones: dict[str, str]) -> dict:
    return {"format": "eurojackpot-analyzer-tickets", "version": 1, "tickets": tickets, "tombstones": tombstones}


class Gist:
    def __init__(self, token: str, gist_id: str | None = None):
        self.token, self.id = token.strip(), gist_id or None

    def _call(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={
            "Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "EuroJackpotAnalyzer", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30, context=tls.context()) as r:
                return json.loads(r.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise SyncError("The GitHub token is not valid (401).") from e
            if e.code == 403:
                raise SyncError("GitHub refused the request (403): the token needs the 'gist' permission.") from e
            if e.code == 404 and self.id:
                raise SyncError("The sync gist was not found (404). Disconnect and connect again.") from e
            raise SyncError(f"GitHub error {e.code} {e.reason}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SyncError(f"No connection to GitHub: {getattr(e, 'reason', e)}") from e

    def pull_or_create(self) -> dict | None:
        """Find (or create) the gist and return its document (None when it was just created)."""
        if not self.id:
            for g in self._call("GET", "/gists?per_page=100") or []:
                if FILE in (g.get("files") or {}):
                    self.id = g["id"]
                    break
            if not self.id:
                g = self._call("POST", "/gists", {"description": DESCRIPTION, "public": False,
                                                  "files": {FILE: {"content": json.dumps(to_doc([], {}))}}})
                self.id = g["id"]
                return None
        g = self._call("GET", f"/gists/{self.id}")
        f = (g.get("files") or {}).get(FILE)
        if not f:
            return None
        text = f.get("content") or ""
        if f.get("truncated"):
            raise SyncError("The sync file is too large.")
        try:
            return json.loads(text) if text.strip() else None
        except ValueError as e:
            raise SyncError("The sync file is damaged.") from e

    def push(self, doc: dict) -> None:
        self._call("PATCH", f"/gists/{self.id}", {"files": {FILE: {"content": json.dumps(doc, ensure_ascii=False)}}})
