"""Shared HTTP client for translation providers.

Each provider used to open a fresh ``httpx.Client`` per request, so every
translation paid for a new TCP connection and a full TLS handshake before a
single byte of text moved. One long-lived client keeps those connections warm
between requests, which is the difference a user feels on a hotkey tool.

``httpx.Client`` is safe to share across threads.
"""

import atexit
import threading
from typing import Optional

import httpx

DEFAULT_TIMEOUT = 15.0

_client: Optional[httpx.Client] = None
_lock = threading.Lock()


def get_client() -> httpx.Client:
    """Returns the process-wide HTTP client, creating it on first use."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = httpx.Client(
                    timeout=DEFAULT_TIMEOUT,
                    follow_redirects=True,
                    limits=httpx.Limits(
                        max_keepalive_connections=8,
                        max_connections=16,
                        keepalive_expiry=90.0,
                    ),
                )
                atexit.register(close_client)
    return _client


def close_client() -> None:
    """Closes the shared client and its pooled connections."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
            _client = None
