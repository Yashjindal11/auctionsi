"""Minimal, hardened JSON-over-HTTP client used by the network adapters."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from auctionsi.errors import AuctionSIError, ValidationError


class HTTPAdapterError(AuctionSIError):
    """A remote agent endpoint failed or returned something unusable."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        raise HTTPAdapterError("redirects are not followed for agent endpoints")


_OPENER = urllib.request.build_opener(_NoRedirect)


def check_base_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError(f"agent URL must be http(s)://host[:port][/path], got {url!r}")
    return url.rstrip("/")


def post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    timeout: float,
    max_bytes: int,
    headers: Mapping[str, str] | None = None,
) -> Any:
    """POST JSON and parse a JSON reply, with a timeout, a size cap and no redirects."""
    body = json.dumps(payload, default=str).encode()
    request = urllib.request.Request(  # noqa: S310 - scheme validated by check_base_url
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise HTTPAdapterError(f"{url} returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPAdapterError(f"{url} unreachable: {exc}") from None
    if len(raw) > max_bytes:
        raise HTTPAdapterError(f"{url} response exceeds {max_bytes} bytes")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPAdapterError(f"{url} did not return JSON") from None
