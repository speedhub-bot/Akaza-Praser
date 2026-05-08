"""DuckDuckGo HTML adapter (html.duckduckgo.com — POST for pagination)."""

from __future__ import annotations

import re
import urllib.parse

from .base import BaseEngine


class DuckDuckGoEngine(BaseEngine):
    name = "duckduckgo"
    homepage = "https://duckduckgo.com"
    method = "POST"
    blocked_phrases = ("rate limit", "too many requests", "anomaly detection")

    def build_url(self, query: str, page: int) -> str:
        # DDG HTML uses a single endpoint; pagination via POST data.
        # We still include ?q= so log inspection / cache-keying are useful.
        encoded = self.encode(query)
        s = page * 30
        return f"https://html.duckduckgo.com/html/?q={encoded}&s={s}"

    def post_data(self, query: str, page: int) -> dict:
        data: dict = {"q": query, "kl": "us-en"}
        if page > 0:
            data.update({
                "s": str(page * 30),
                "dc": str(page * 30 + 1),
                "v": "l",
                "o": "json",
                "api": "/d.js",
            })
        return data

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "a.result__a[href]",
            "h2.result__title a[href]",
            "article[data-testid='result'] a[href]",
            "div.result__body a.result__a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                if href.startswith("//"):
                    href = "https:" + href
                if "uddg=" in href:
                    m = re.search(r"uddg=([^&]+)", href)
                    if m:
                        href = urllib.parse.unquote(m.group(1))
                if (
                    href.startswith("http")
                    and "duckduckgo.com" not in href
                ):
                    out.append(href)
        if len(out) < 3:
            for m in re.finditer(r"uddg=(https?[^&\"<>\s]+)", html):
                out.append(urllib.parse.unquote(m.group(1)))
        return self._dedupe_keep_order(out)
