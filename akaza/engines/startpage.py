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
        # Startpage's modern endpoint is /sp/search; the legacy /do/search
        # 302s to consent. ``page=N`` is 1-indexed.
        n = page + 1
        return (
            f"https://www.startpage.com/sp/search?query={encoded}"
            f"&page={n}&cat=web&language=english&abp=1"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        # Modern Startpage uses Emotion-style class names like
        # `result-title css-1bggj8v` where the css-XXXXXX hash rotates with
        # every deploy. We anchor to the stable, semantic class names only.
        for sel in (
            "a.result-link[href]",
            "a.result-title[href]",
            "a.wgl-site-title[href]",
            "a.wgl-display-url[href]",
            "a.favicon-link[href]",
            # Legacy selectors (older Startpage themes).
            "a.w-gl__result-url[href]",
            "a.w-gl__result-title[href]",
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
