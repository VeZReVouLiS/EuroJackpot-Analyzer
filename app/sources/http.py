"""Shared HTTP helper with browser-like headers and readable errors."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .. import tls

# Some sites (Akamai bot protection) reject unknown clients -> look like a normal browser.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class SourceError(ConnectionError):
    """Network/HTTP failure of a data source; message is safe to show to the user."""


def headers_for(referer: str) -> dict:
    origin = referer.rstrip("/")
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
        "Origin": origin,
        "Referer": referer,
    }


def get_json(url: str, referer: str, retries: int = 3, timeout: int = 25):
    """GET url and parse JSON ('' / 204 -> None). Raises SourceError with HTTP status / reason."""
    req = urllib.request.Request(url, headers=headers_for(referer))
    last = ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=tls.context()) as r:
                body = r.read().decode("utf-8")
                return json.loads(body) if body.strip() else None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.reason}"
            if e.code in (400, 404):      # not retryable
                break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            reason = getattr(e, "reason", e)
            last = f"{type(e).__name__}: {reason}"
        time.sleep(0.8 * (attempt + 1))
    raise SourceError(last)
