"""Ecosia — Bing-backed, lighter blocking."""

from __future__ import annotations

from .base import BaseEngine


class EcosiaEngine(BaseEngine):
    name = "ecosia"
    homepage = "https://www.ecosia.org"
    prefer_curl = True
    blocked_phrases = ("captcha required", "access denied")

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        # Ecosia paginates via ``p=`` (zero-indexed).
        return f"https://www.ecosia.org/search?q={encoded}&p={page}"

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "article.result a.result__link[href]",
            "article.result a.result-url[href]",
            "div.mainline-results article a[href]",
            "a.result__link[href]",
            "a[data-test-id='result-link']",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "ecosia.org" not in href:
                    out.append(href)
        return self._dedupe_keep_order(out)
