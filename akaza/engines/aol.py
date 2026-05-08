"""AOL Search (Yahoo-backed)."""

from __future__ import annotations

import re
import urllib.parse

from .base import BaseEngine


class AOLEngine(BaseEngine):
    name = "aol"
    homepage = "https://search.aol.com"
    prefer_curl = True
    blocked_phrases = ("captcha", "are you a robot", "guce.aol.com")

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        b = page * 10 + 1
        return f"https://search.aol.com/aol/search?q={encoded}&b={b}"

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "h3.title a[href]",
            "div.compTitle a[href]",
            "a.ac-algo[href]",
            "div.algo-sr a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                m = re.search(r"[?&/]RU=([^&\s]+)", href)
                if m:
                    cand = re.sub(
                        r"/(?:RK|RS|RB|RT|RX|RQ)=.*$", "", m.group(1)
                    )
                    href = urllib.parse.unquote(cand)
                if href.startswith("http") and "aol.com" not in href:
                    out.append(href)
        return self._dedupe_keep_order(out)
