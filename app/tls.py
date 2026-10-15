"""TLS context for every outgoing request.

The Python that is bundled into the macOS app has no root certificates of its own (python.org builds ship none,
the system keychain is not used by OpenSSL), so every HTTPS request failed with CERTIFICATE_VERIFY_FAILED.
The default context (system store, where available) is therefore extended with the certifi bundle."""
from __future__ import annotations

import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except Exception:          # certifi missing or unreadable: keep the default store
        pass
    return ctx
