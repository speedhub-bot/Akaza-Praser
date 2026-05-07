"""Startpage — Google results, no Google fingerprint surface."""

from __future__ import annotations

from .base import BaseEngine


class StartpageEngine(BaseEngine):
    name = "startpage"
    homepage = "https://www.startpage.com"
    prefer_curl = True
    blocked_phrases = ("captcha", "access denied")

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        # Startpage uses ``page=N`` (1-indexed). Try anonymous form mode.
        n = page + 1
        return (
            f"https://www.startpage.com/do/search?q={encoded}"
            f"&page={n}&cat=web&pl=opensearch&language=english&abp=1"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "a.w-gl__result-url[href]",
            "a.w-gl__result-title[href]",
            "div.w-gl__result a[href]",
            "section.w-gl div.search-result a[href]",
            "h2.w-gl__result-title a[href]",
            "a.search-item__link[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if (
                    href and href.startswith("http")
                    and "startpage.com" not in href
                ):
                    out.append(href)
        return self._dedupe_keep_order(out)
