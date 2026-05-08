"""Brave Search — independent index, low blocking, supports operators."""

from __future__ import annotations

from .base import BaseEngine


class BraveEngine(BaseEngine):
    name = "brave"
    homepage = "https://search.brave.com"
    prefer_curl = True
    blocked_phrases = (
        "rate limit",
        "you've been rate limited",
        "<title>access denied</title>",
    )

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        # Brave uses 1-indexed offset of 20 results per page.
        offset = page
        return (
            f"https://search.brave.com/search?q={encoded}"
            f"&offset={offset}&source=web&spellcheck=0"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "div.snippet a.h[href]",
            "div.snippet[data-type='web'] a[href]",
            "div.snippet a.result-header[href]",
            "a.result-header[href]",
            "div#results div.snippet a[href]",
            "main a.h[href]",
            "a[data-testid='web-result-title-link'][href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "brave.com" not in href:
                    out.append(href)
        if len(out) < 5:
            out += self._regex_external_urls(
                html, ["brave.com", "bravesearch.com"]
            )
        return self._dedupe_keep_order(out)
