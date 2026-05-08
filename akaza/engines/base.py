"""Engine ABC and shared helpers.

Every engine adapter implements:
    - ``name`` (class attribute)
    - ``build_url(query, page) -> str``
    - ``extract(html) -> list[str]``
    - ``is_blocked(html) -> bool``  (optional)
    - ``method`` / ``post_data(query, page)``  (optional, for POST engines)
"""

from __future__ import annotations

import re
import urllib.parse
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup


class BaseEngine(ABC):
    """Abstract base class for a search-engine adapter."""

    name: str = "base"
    homepage: str = ""
    method: str = "GET"
    prefer_curl: bool = False  # True => use curl_cffi for TLS impersonation
    blocked_phrases: tuple[str, ...] = ()
    soft_block_phrases: tuple[str, ...] = ()  # 200 OK but empty/no results

    # ------------------------------------------------------------------
    @abstractmethod
    def build_url(self, query: str, page: int) -> str:
        """Return the SERP URL for ``query`` at zero-indexed ``page``."""

    @abstractmethod
    def extract(self, html: str) -> list[str]:
        """Return result URLs found in ``html``."""

    # ------------------------------------------------------------------

    def post_data(self, query: str, page: int) -> dict | None:
        return None

    def is_blocked(self, html: str) -> bool:
        if not html:
            return True
        low = html.lower()
        for phrase in self.blocked_phrases:
            if phrase in low:
                return True
        return False

    def is_empty(self, html: str) -> bool:
        if not html:
            return True
        low = html.lower()
        for phrase in self.soft_block_phrases:
            if phrase in low:
                return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def _absolute(self, href: str) -> str | None:
        if not href:
            return None
        href = href.strip()
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("http"):
            return href
        if href.startswith("/") and self.homepage:
            return self.homepage.rstrip("/") + href
        return None

    def _dedupe_keep_order(self, urls: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    # Common boilerplate URLs that any HTML page may carry: XML namespaces,
    # CDN/asset hosts, tracking pixels, browser-extension store links, schema
    # microdata, social/share scaffolding, etc. These are NEVER organic SERP
    # results so we always strip them from regex backstops.
    _GLOBAL_NOISE_SUBSTRS: tuple[str, ...] = (
        "w3.org/",
        "schema.org",
        "ogp.me",
        "purl.org",
        "xmlns.",
        "chrome.google.com/webstore",
        "addons.mozilla.org/",
        "apps.apple.com/",
        "play.google.com/store/apps",
        "itunes.apple.com/",
        "googletagmanager.com",
        "google-analytics.com",
        "googletagservices.com",
        "googleadservices.com",
        "googlesyndication.com",
        "doubleclick.net",
        "facebook.com/sharer",
        "facebook.com/tr",
        "twitter.com/share",
        "twitter.com/intent",
        "x.com/share",
        "x.com/intent",
        "linkedin.com/share",
        "pinterest.com/pin/create",
        "reddit.com/submit",
        "telegram.me/share",
        "t.me/share",
        "wa.me/?text=",
        "whatsapp.com/send",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "gstatic.com",
        "ajax.googleapis.com",
        "cdnjs.cloudflare.com",
        "cdn.jsdelivr.net",
        "unpkg.com/",
        "github.com/marginaliasearch",
        "github.com/marginaliasearch/submit-site",
        "creativecommons.org/licenses",
    )

    # Generic regex backstop used by a few extractors.
    @classmethod
    def _regex_external_urls(
        cls, html: str, exclude_substrings: list[str]
    ) -> list[str]:
        urls = re.findall(r"https?://[^\s\"'<>]{10,}", html or "")
        excludes = tuple(s.lower() for s in exclude_substrings) + cls._GLOBAL_NOISE_SUBSTRS
        out = []
        for u in urls:
            low = u.lower()
            if any(s in low for s in excludes):
                continue
            out.append(u.rstrip(".,;:)]}>'\""))
        return out

    @staticmethod
    def encode(query: str) -> str:
        return urllib.parse.quote_plus(query)
