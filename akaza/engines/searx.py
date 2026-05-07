"""SearXNG aggregator — rotates across multiple public instances.

A SearXNG instance proxies search to many engines simultaneously. Public
instances rotate availability, so we keep a list and round-robin through it.
The ``build_url`` helper picks the next instance.
"""

from __future__ import annotations

import random
from threading import Lock

from .base import BaseEngine

# Public SearXNG instances known to expose the legacy HTML form.
# Order is randomised at import time for variety across runs.
PUBLIC_INSTANCES: list[str] = [
    "https://searx.be",
    "https://searx.tiekoetter.com",
    "https://searx.work",
    "https://search.disroot.org",
    "https://searx.ngn.tf",
    "https://search.bus-hit.me",
    "https://searx.ankervalley.com",
    "https://searxng.world",
    "https://baresearch.org",
    "https://search.inetol.net",
]
random.shuffle(PUBLIC_INSTANCES)


class SearxEngine(BaseEngine):
    name = "searx"
    homepage = "https://searx.be"
    prefer_curl = False
    blocked_phrases = ("rate-limited", "rate limit", "too many requests")

    def __init__(self, instances: list[str] | None = None) -> None:
        self._lock = Lock()
        self._instances = list(instances or PUBLIC_INSTANCES)
        self._idx = 0

    def _next_instance(self) -> str:
        with self._lock:
            inst = self._instances[self._idx % len(self._instances)]
            self._idx += 1
            return inst

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        inst = self._next_instance()
        return (
            f"{inst}/search?q={encoded}&pageno={page + 1}&format=html"
            "&categories=general&language=en"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "article.result h3 a[href]",
            "article.result-default a.url_wrapper[href]",
            "div.result h3 a[href]",
            "h3 a[href]",
            "a.url_header[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http"):
                    out.append(href)
        # Drop instance domains from results
        instance_hosts = [i.split("//", 1)[-1] for i in self._instances]
        out = [u for u in out if not any(h in u for h in instance_hosts)]
        return self._dedupe_keep_order(out)
