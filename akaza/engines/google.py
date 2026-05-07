"""Google Search adapter (HTML SERP, requires good fingerprint)."""

from __future__ import annotations

import re
import urllib.parse

from .base import BaseEngine


class GoogleEngine(BaseEngine):
    name = "google"
    homepage = "https://www.google.com"
    prefer_curl = True
    blocked_phrases = (
        "unusual traffic from your computer",
        "our systems have detected",
        "/sorry/index?",
        "captcha",
    )

    def build_url(self, query: str, page: int) -> str:
        encoded = self.encode(query)
        return (
            f"https://www.google.com/search?q={encoded}"
            f"&num=10&start={page * 10}&hl=en&pws=0"
        )

    def extract(self, html: str) -> list[str]:
        soup = self._soup(html)
        out: list[str] = []
        for sel in (
            "div.yuRUbf > a[href]",
            "div.yuRUbf a[jsname][href]",
            "div.tF2Cxc a[href]",
            "div.g a[href]",
            "a[jsname='UWckNb'][href]",
            "div[data-hveid] a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "google." not in href:
                    out.append(href)
        # /url?q= redirects
        for a in soup.select("a[href^='/url?']"):
            href = a.get("href", "")
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("q", [])
            if q and q[0].startswith("http"):
                out.append(q[0])
        # Regex fallback: capture any external URL out of double-quoted attrs.
        if len(out) < 5:
            out += re.findall(
                r'"(https?://(?!\S*google\.com)(?!\S*googleusercontent)[^"\s<>]{10,})"',
                html,
            )
        return self._dedupe_keep_order(out)
