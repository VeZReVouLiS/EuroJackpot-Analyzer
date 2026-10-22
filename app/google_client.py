"""The identity of this app for "Sign in with Google" (Google Cloud project "EuroJackpot Analyzer").

The client id is public (it is visible in every sign-in URL). The client secret of an installed (desktop) app is not a real secret
according to Google, but it is kept out of the public repository on purpose: it is written to `app/_google_secret.py` (git-ignored)
by the build (a GitHub Actions secret on the CI, a local file on the developer PC) and bundled into the app.
"""
from __future__ import annotations

import os

CLIENT_ID = "525620810871-jghtig793k6kev3lk1fn6p2cu050usia.apps.googleusercontent.com"     # Desktop client
WEB_CLIENT_ID = "525620810871-0kr1mrcnetva3g01dgogna3ahlsrqo1d.apps.googleusercontent.com"   # Web client (web app / iPhone)


def client_secret() -> str:
    try:
        from ._google_secret import SECRET          # type: ignore[import-not-found]
    except ImportError:
        return os.environ.get("EJ_GOOGLE_SECRET", "")
    return SECRET


def available() -> bool:
    """Google sign-in only works in builds that carry the client secret."""
    return bool(CLIENT_ID and client_secret())
