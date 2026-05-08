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
        # Bing's modern SERP wraps every result in `a.tilk` whose `href` is a
        # `bing.com/ck/a?u=a1<base64>` redirect. The cleaner pipeline unwraps
        # those, so we must NOT filter them out here.
        for sel in (
            "a.tilk[href]",
            "li.b_algo h2 a[href]",
            "li.b_algo .b_title a[href]",
            "#b_results li.b_algo a[href]",
            "div.b_caption a[href]",
            "div.b_algoheader a[href]",
        ):
            for a in soup.select(sel):
                href = a.get("href")
                if not href or not href.startswith("http"):
                    continue
                # Keep ck/a redirects (cleaner unwraps them); drop other bing.com.
                if "bing.com" in href and "/ck/a" not in href:
                    continue
                out.append(href)
        # Visible URLs in <cite> tags as a backstop ("example.com / path / page").
        for c in soup.find_all("cite"):
            text = c.get_text(strip=True).replace(" \u203a ", "/")
            text = text.replace("\u203a", "/")
            text = re.sub(r"\s+", "", text)
            if text.startswith("http"):
                out.append(text)
        if len(out) < 3:
            out += re.findall(
                r'href="(https?://(?!\S*\.bing\.com)[^"\s<>]{10,})"', html
            )
        return self._dedupe_keep_order(out)
