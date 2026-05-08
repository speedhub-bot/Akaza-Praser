"""Bing Search adapter."""

from __future__ import annotations

import re

from .base import BaseEngine


class BingEngine(BaseEngine):
    name = "bing"
    homepage = "https://www.bing.com"
    prefer_curl = True
    blocked_phrases = (
        "access denied",
        "unusual traffic",
        "captcha",
        "/cf-error",
    )
    soft_block_phrases = (
        "no results found for",
        "we don't have any results",
    )

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        first = page * 10 + 1
        return (
            f"https://www.bing.com/search?q={encoded}"
            f"&first={first}&FORM=PERE&setlang=en"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "li.b_algo h2 a[href]",
            "li.b_algo .b_title a[href]",
            "li.b_algo a.tilk[href]",
            "#b_results li.b_algo a[href]",
            "div.b_caption a[href]",
            "div.b_algoheader a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "bing.com" not in href:
                    out.append(href)
        if len(out) < 3:
            out += re.findall(
                r'href="(https?://(?!\S*bing\.com)[^"\s<>]{10,})"', html
            )
        return self._dedupe_keep_order(out)
