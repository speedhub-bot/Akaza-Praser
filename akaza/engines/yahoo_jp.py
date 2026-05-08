"""Yahoo! JAPAN search."""

from __future__ import annotations

import re

from .base import BaseEngine


class YahooJPEngine(BaseEngine):
    name = "yahoo_jp"
    homepage = "https://search.yahoo.co.jp"
    prefer_curl = True
    blocked_phrases = (
        "ロボットではないことを確認",
        "are you a robot",
        "denied",
    )

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        b = page * 10 + 1
        return f"https://search.yahoo.co.jp/search?p={encoded}&b={b}"

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "div.sw-Card__title a[href]",
            "div.ContentWrapper a[href]",
            "div.swof_title a[href]",
            "h3.sw-Card__title a[href]",
            "section a.sw-Card__titleInner[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href", "")
                if (
                    href.startswith("http")
                    and "yahoo.co.jp" not in href
                    and "yimg.jp" not in href
                ):
                    out.append(href)
        if len(out) < 3:
            raw = re.findall(
                r'href="(https?://(?!(?:[^/]*\.)?yahoo\.co\.jp)'
                r'(?!(?:[^/]*\.)?yimg\.jp)[^"<>\s]{10,})"',
                html,
            )
            out += raw
        return self._dedupe_keep_order(out)
