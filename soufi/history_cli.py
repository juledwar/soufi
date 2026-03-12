# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates
# All rights reserved.

"""Simple CLI for package release history lookups."""

from __future__ import annotations

import os
from typing import Any

from soufi import finder

DEFAULT_CACHE_PATH = "~/.cache/soufi-history.dbm"
DEFAULT_CACHE_TTL = 60 * 60 * 24

HISTORY_TYPES = {
    "python": finder.SourceType.python,
    "npm": finder.SourceType.npm,
    "gem": finder.SourceType.gem,
    "crate": finder.SourceType.crate,
    "go": finder.SourceType.go,
    "java": finder.SourceType.java,
}


def get_release_history(
    distro: str,
    name: str,
    cache_path: str,
    cache_ttl: int,
    timeout: int,
    pyindex: str,
    goproxy: str,
) -> list[dict[str, Any]]:
    """Return release history for the requested package."""
    if distro not in HISTORY_TYPES:
        raise ValueError(f"Unsupported distro/type: {distro}")

    cache_file = os.path.expanduser(cache_path)
    os.makedirs(os.path.dirname(cache_file) or ".", exist_ok=True)
    kwargs: dict[str, Any] = {
        "name": name,
        "s_type": HISTORY_TYPES[distro],
        "cache_backend": "dogpile.cache.dbm",
        "cache_args": {"filename": cache_file},
        "cache_ttl": cache_ttl,
        "timeout": timeout,
    }
    if distro == "python":
        kwargs["pyindex"] = pyindex
    if distro == "go":
        kwargs["goproxy"] = goproxy
    source_finder = finder.factory(distro, **kwargs)
    return source_finder.get_release_history()
