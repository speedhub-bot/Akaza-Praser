"""Yahoo Search (US)."""

from __future__ import annotations

import re
import urllib.parse

from .base import BaseEngine


class YahooEngine(BaseEngine):
    name = "yahoo"
    homepage = "https://search.yahoo.com"
    prefer_curl = True
    blocked_phrases = (
        "consent.yahoo.com",
        "guce.yahoo.com",
        "are you a robot",
        "sign in to confirm",
    )

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        b = page * 10 + 1
        return (
            f"https://search.yahoo.com/search?p={encoded}"
            f"&b={b}&vl=lang_en&fr=opensearch"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for a in soup.select("a[data-ru], a[data-rurl], a[data-legacyurl]"):
            for attr in ("data-ru", "data-rurl", "data-legacyurl"):
                v = a.get(attr)
                if v and v.startswith("http"):
                    out.append(urllib.parse.unquote(v))
        for sel in (
            "div#web ol li div.compTitle a[href]",
            "div.algo-sr a[href]",
            "h3.title a[href]",
            "div.Sr a[href]",
            "li.algo div.compTitle a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href:
                    out.append(href)
        for m in re.finditer(r"/RU=([^/]+)/", html):
            cand = urllib.parse.unquote(m.group(1))
            if cand.startswith("http"):
                out.append(cand)
        # Drop yahoo internals
        out = [
            u for u in out
            if u.startswith("http") and "yahoo." not in u and "yimg." not in u
        ]
        return self._dedupe_keep_order(out)
