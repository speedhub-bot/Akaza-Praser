"""Marginalia — hand-curated index of small/old/long-form web."""

from __future__ import annotations

from .base import BaseEngine


class MarginaliaEngine(BaseEngine):
    name = "marginalia"
    homepage = "https://search.marginalia.nu"
    blocked_phrases = ()

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        # Marginalia uses ``js=no-js&page=N`` (1-indexed) for the legacy form.
        return (
            f"https://search.marginalia.nu/search?query={encoded}"
            f"&profile=no-js&js=default&page={page + 1}"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "section.search-result h2 a[href]",
            "div.search-result h2 a[href]",
            "article.search-result a.title[href]",
            "h2 a[href]",
            "a.url[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if (
                    href and href.startswith("http")
                    and "marginalia.nu" not in href
                ):
                    out.append(href)
        return self._dedupe_keep_order(out)
