"""Optional REST/WebSocket API and dashboard host (``pip install "auctionsi[api]"``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from auctionsi.errors import OptionalDependencyError

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_app(*args: Any, **kwargs: Any) -> FastAPI:
    try:
        from auctionsi.api.app import create_app as _create
    except ImportError as exc:
        raise OptionalDependencyError(
            'the API needs FastAPI: pip install "auctionsi[api]"'
        ) from exc
    return _create(*args, **kwargs)


__all__ = ["create_app"]
