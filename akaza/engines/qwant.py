"""Qwant — Bing+own EU index."""

from __future__ import annotations

from .base import BaseEngine


class QwantEngine(BaseEngine):
    name = "qwant"
    homepage = "https://www.qwant.com"
    prefer_curl = True
    blocked_phrases = ("access denied", "captcha")

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        offset = page * 10
        return (
            f"https://www.qwant.com/?q={encoded}"
            f"&t=web&l=en&s=10&o={offset}"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "a[data-testid='serTitle'][href]",
            "a.WebResult-module__title[href]",
            "div.web a[href]",
            "section[data-testid='webResults'] a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "qwant.com" not in href:
                    out.append(href)
        if len(out) < 3:
            out += self._regex_external_urls(html, ["qwant.com", "qwantjunior"])
        return self._dedupe_keep_order(out)
