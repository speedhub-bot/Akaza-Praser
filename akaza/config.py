"""Central config + blocklists for the Akaza Dork Parser.

Everything tunable lives here. ``Settings`` is the runtime config dataclass;
the module-level constants are static reference data the rest of the package
imports.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
DORKS_FILE = os.path.join(SCRIPT_DIR, "dorks.txt")
PROXIES_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")


# ---------------------------------------------------------------------------
# User Agent pool — modern Chrome/Firefox/Safari/Edge across desktop OSes.
# Used as a fallback when the curl_cffi impersonation isn't available.
# ---------------------------------------------------------------------------

USER_AGENTS: tuple[str, ...] = (
    # Chrome 131 / Linux (matches our default curl_cffi impersonate target)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome 130 / 129 — for variety across pool
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Edge 131
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Firefox 132 / 131
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Safari 18 / 17
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Chrome on Android — handy for engines that vary by mobile/desktop split
    "Mozilla/5.0 (Linux; Android 14; SM-S928U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
)


# ---------------------------------------------------------------------------
# Sec-CH-UA strings paired with a few common Chrome major versions.
# Picked together with a UA so the headers stay self-consistent.
# ---------------------------------------------------------------------------

SEC_CH_UA_BY_CHROME: dict[str, str] = {
    "131": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "130": '"Google Chrome";v="130", "Chromium";v="130", "Not?A_Brand";v="99"',
    "129": '"Not=A?Brand";v="8", "Chromium";v="129", "Google Chrome";v="129"',
}


# ---------------------------------------------------------------------------
# Domains we never want in the output. Anything matching by exact host or
# trailing ``.suffix`` is dropped. These are search-engine internals,
# tracking infra, social, and *huge* sites that pollute results.
# ---------------------------------------------------------------------------

BLOCKED_DOMAINS: frozenset[str] = frozenset({
    # Google
    "google.com", "google.co.uk", "google.de", "google.fr", "google.es",
    "googleusercontent.com", "gstatic.com", "googleapis.com",
    "youtube.com", "ytimg.com", "googlevideo.com", "googletagmanager.com",
    "googleadservices.com", "googlesyndication.com", "doubleclick.net",
    # Bing / Microsoft
    "bing.com", "microsoft.com", "msn.com", "live.com", "windows.com",
    "office.com", "office365.com", "azureedge.net",
    # Yahoo (US + JP) and AOL
    "yahoo.com", "yimg.com", "yahooapis.com", "r.search.yahoo.com",
    "search.yahoo.com", "yahoo.co.jp", "search.yahoo.co.jp",
    "auctions.yahoo.co.jp", "shopping.yahoo.co.jp", "news.yahoo.co.jp",
    "map.yahoo.co.jp", "btoptout.yahoo.co.jp", "login.yahoo.co.jp",
    "kisekae.yahoo.co.jp", "s.yimg.jp", "yimg.jp",
    "aol.com", "search.aol.com",
    # DuckDuckGo
    "duckduckgo.com", "duckduckstatic.com",
    # Other engines we go through
    "search.brave.com", "brave.com", "mojeek.com", "startpage.com",
    "yandex.com", "yandex.ru", "yastatic.net", "ecosia.org", "qwant.com",
    "searx.be", "searx.tiekoetter.com", "searx.work", "search.disroot.org",
    "search.marginalia.nu", "marginalia.nu",
    # Social / link-shorteners
    "facebook.com", "fb.com", "fbcdn.net", "instagram.com",
    "twitter.com", "x.com", "twimg.com", "t.co", "linkedin.com",
    "pinterest.com", "tiktok.com", "snapchat.com", "reddit.com", "redd.it",
    "bit.ly", "ow.ly", "tinyurl.com", "goo.gl", "lnkd.in",
    # Mega sites that make for low-signal dork hits
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es",
    "wikipedia.org", "wikimedia.org", "stackoverflow.com",
    # Tech infra noise
    "cloudflare.com", "akamai.com", "akamaihd.net",
    "w3.org", "schema.org", "opengraph.io", "github.com",
})


# ---------------------------------------------------------------------------
# File extensions we never want as result URLs (assets, archives, video,
# fonts, etc.).
# ---------------------------------------------------------------------------

BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".css", ".js", ".mjs", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tiff",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".xml", ".rss", ".atom",
    ".gz", ".zip", ".tar", ".rar", ".7z", ".bz2", ".xz",
    ".mp4", ".mp3", ".avi", ".mov", ".mkv", ".webm",
    ".swf", ".wav", ".ogg", ".flac", ".m4a", ".m4v",
    ".pdf",  # rarely a dork-quality URL
})


# Tracking / referral params we strip from the cleaned URL.
TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_brand",
    "gclid", "fbclid", "msclkid", "yclid", "dclid",
    "_ga", "_gid", "_gl", "mc_eid", "mc_cid",
    "ref", "referrer", "source", "trk", "trkCampaign", "src",
})


# Extensions that are POSITIVE signal of a dynamic / interesting page.
SIGNAL_EXTENSIONS: frozenset[str] = frozenset({
    ".php", ".php3", ".php4", ".php5", ".phtml",
    ".asp", ".aspx", ".ashx", ".asmx",
    ".jsp", ".jsf", ".do", ".action",
    ".cfm", ".cgi", ".pl",
    ".shtml",
    # Plain html/htm are kept in the quality scorer (lower weight)
})


# Path tokens that often indicate parameterized / dorkable pages.
SIGNAL_PATH_KEYWORDS: tuple[str, ...] = (
    "index.php", "view.php", "item.php", "product.php", "category.php",
    "search.php", "detail.php", "details.php", "article.php", "news.php",
    "download.php", "profile.php", "login.php", "cart.php", "checkout.php",
    "order.php", "admin.php", "show.php", "page.php", "shop.php",
    "store.php", "buy.php", "offer.php", "deal.php",
    "viewproduct", "viewitem", "viewcategory", "showproduct",
    "displayproduct", "productdetails",
)


# Domain hints that are usually low-signal *for dorks* (CDN docs, blogs).
LOW_QUALITY_HOSTS: frozenset[str] = frozenset({
    "medium.com", "dev.to", "hashnode.dev", "substack.com",
    "blogspot.com", "wordpress.com", "tumblr.com",
    "issuu.com", "scribd.com", "slideshare.net",
    "academia.edu", "researchgate.net",
})


# ---------------------------------------------------------------------------
# Engine roster (string identifiers; the actual classes live in ``akaza.engines``).
# Order = preference order. The CLI accepts engine names case-insensitively.
# ---------------------------------------------------------------------------

ENGINE_NAMES: tuple[str, ...] = (
    # Tier 1: low-blocking, high-quality independent indexes
    "brave", "mojeek", "marginalia", "startpage", "ecosia", "qwant",
    # Tier 2: SearXNG aggregators (rotates instances)
    "searx",
    # Tier 3: classic engines that tend to block harder
    "duckduckgo", "yandex", "yahoo", "yahoo_jp", "aol",
    # Tier 4: usually requires curl_cffi + good proxies
    "bing", "google",
)

# Sensible default if user doesn't pick engines: ones that mostly work
# without proxies in proxyless mode.
DEFAULT_ENGINES: tuple[str, ...] = (
    "brave", "mojeek", "marginalia", "ecosia", "qwant",
    "searx", "duckduckgo", "yahoo_jp",
)


# ---------------------------------------------------------------------------
# Settings dataclass — runtime config the CLI / TUI mutates.
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    """Runtime configuration for one parser run."""

    # Concurrency / pacing
    concurrency: int = 24                 # parallel dork x engine workers
    per_engine_concurrency: int = 3       # parallel page fetches per engine
    max_pages: int = 8                    # pages per engine per dork
    fast_mode: bool = True                # smaller jitter between requests

    # URL filtering
    php_only: bool = False                # only emit URLs with .php-family ext
    require_query: bool = False           # only emit URLs with ?param=
    unique_sites_only: bool = False       # one URL per netloc
    quality_threshold: float = 0.40       # 0..1 minimum from quality scorer
    apply_dork_suffix: bool = True        # use the legacy `text .ext?param=` filter

    # Engines
    engines: list[str] = field(default_factory=lambda: list(DEFAULT_ENGINES))

    # Proxies
    proxy_mode: str = "proxyless"         # proxyless | file | online
    proxy_protocol: str = "http"          # http | socks4 | socks5
    proxy_validate: bool = True

    # HTTP / TLS
    use_curl_cffi: bool = True            # impersonate Chrome 131 JA3 if installed
    request_timeout: float = 22.0
    max_retries: int = 3

    # Locale
    accept_language: str = "en-US,en;q=0.9"
    region: str = "us"

    # Output
    output_dir: str = RESULTS_DIR

    # Optional Selenium engine (kept for parity with old script)
    chrome_engine: bool = False
    chrome_headless: bool = True

    def normalised_engines(self) -> list[str]:
        return [e.strip().lower() for e in self.engines if e and e.strip()]


# ---------------------------------------------------------------------------
# Tiny helpers used across the package.
# ---------------------------------------------------------------------------


def read_lines(path: str, *, strip_comments: bool = True) -> list[str]:
    """Read a text file into a list of stripped, non-empty lines."""
    if not os.path.exists(path):
        return []
    out: list[str] = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if strip_comments and s.startswith("#"):
                continue
            out.append(s)
    return out


def append_lines(path: str, lines: Iterable[str]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
