"""URL allow/deny filter and a thread-safe deduping store."""

from __future__ import annotations

import os
import urllib.parse
from threading import Lock

from .cleaner import normalise
from .config import BLOCKED_DOMAINS, BLOCKED_EXTENSIONS, SIGNAL_EXTENSIONS


class URLFilter:
    """Cheap allow/deny filter used as a first pass before quality scoring."""

    def __init__(
        self,
        *,
        php_only: bool = False,
        require_query: bool = False,
        blocked_domains: frozenset[str] | None = None,
    ) -> None:
        self.php_only = php_only
        self.require_query = require_query
        self.blocked_domains = blocked_domains or BLOCKED_DOMAINS

    def is_valid(self, url: str) -> bool:
        if not url or not url.startswith("http"):
            return False
        try:
            pr = urllib.parse.urlparse(url)
        except Exception:
            return False
        netloc = (pr.netloc or "").lower()
        if not netloc or "." not in netloc:
            return False
        host = netloc.split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        for b in self.blocked_domains:
            if host == b or host.endswith("." + b):
                return False
        path = (pr.path or "").lower()
        ext = ""
        if "." in os.path.basename(path):
            ext = os.path.splitext(path.split("?")[0])[1].lower()
        if ext in BLOCKED_EXTENSIONS:
            return False
        if self.php_only and ext not in SIGNAL_EXTENSIONS and not path.endswith(".php"):
            return False
        if self.require_query and not pr.query:
            return False
        return True


class URLStore:
    """Thread-safe set of normalised URLs (and per-host bookkeeping)."""

    def __init__(self, *, unique_site_only: bool = False) -> None:
        self._lock = Lock()
        self._urls: set[str] = set()
        self._domains: set[str] = set()
        self.unique_site_only = unique_site_only

    def __len__(self) -> int:
        with self._lock:
            return len(self._urls)

    def __contains__(self, url: str) -> bool:
        norm = normalise(url)
        with self._lock:
            return norm in self._urls

    def add(self, url: str) -> bool:
        """Add a URL. Returns True if it was newly inserted."""
        try:
            norm = normalise(url)
        except Exception:
            return False
        if not norm:
            return False
        host = urllib.parse.urlparse(norm).netloc
        with self._lock:
            if self.unique_site_only and host in self._domains:
                return False
            if norm in self._urls:
                return False
            self._urls.add(norm)
            self._domains.add(host)
            return True

    def all(self) -> list[str]:
        with self._lock:
            return sorted(self._urls)
