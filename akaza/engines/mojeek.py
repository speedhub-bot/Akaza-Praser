"""Mojeek — independent crawler, almost never blocks, deep niche pages."""

from __future__ import annotations

from .base import BaseEngine


class MojeekEngine(BaseEngine):
    name = "mojeek"
    homepage = "https://www.mojeek.com"
    blocked_phrases = ("captcha required", "access denied")

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        # Mojeek uses ``s=`` for offset (1-indexed) with 10 per page.
        s = page * 10 + 1
        return f"https://www.mojeek.com/search?q={encoded}&s={s}&fmt=html"

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "ul.results-standard li > h2 > a[href]",
            "ul.results-standard li a.ob[href]",
            "a.ob[href]",
            "div#results li a[href]",
            "h2 a.title[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "mojeek.com" not in href:
                    out.append(href)
        return self._dedupe_keep_order(out)
