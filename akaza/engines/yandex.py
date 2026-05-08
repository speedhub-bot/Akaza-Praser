"""Yandex Search — different index, low blocking outside RU/UA."""

from __future__ import annotations

import re

from .base import BaseEngine


class YandexEngine(BaseEngine):
    name = "yandex"
    homepage = "https://yandex.com"
    prefer_curl = True
    blocked_phrases = (
        "showcaptcha?",
        "are you not a robot",
        "smartcaptcha",
    )

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        return (
            f"https://yandex.com/search/?text={encoded}"
            f"&p={page}&lr=10393"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "li.serp-item a.organic__url[href]",
            "li.serp-item a.Link.Link_theme_normal[href]",
            "li.serp-item h2 a[href]",
            "a.OrganicTitle-Link[href]",
            "a.Link[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                if href.startswith("http") and "yandex." not in href:
                    out.append(href)
                    continue
                # /clck/jsredir?...&to=<url>
                m = re.search(r"[?&]to=(https?[^&\s]+)", href)
                if m:
                    out.append(m.group(1))
        # Fallback regex sweep — handle both `&to=` and HTML-escaped `&amp;to=`.
        out += re.findall(r"(?:&amp;|&|\?)to=(https?[^&\"'<>\s]+)", html)
        return self._dedupe_keep_order(out)
