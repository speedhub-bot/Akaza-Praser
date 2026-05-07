import os
import sys
import asyncio
import random
import re
import time
import urllib.parse
import base64
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from threading import Lock

import aiohttp
from aiohttp_socks import ProxyConnector
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
from duckduckgo_search import DDGS

# Selenium imports (optional - only loaded if Chrome engine selected)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False

init(autoreset=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
DORKS_FILE = os.path.join(SCRIPT_DIR, "dorks.txt")
PROXIES_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

BLOCKED_DOMAINS = {
    "google.com", "googleusercontent.com", "gstatic.com", "googleapis.com",
    "youtube.com", "ytimg.com", "googlevideo.com",
    "bing.com", "microsoft.com", "msn.com", "live.com", "windows.com",
    "yahoo.com", "yimg.com", "yahooapis.com",
    # Block all Yahoo Japan internal domains
    "yahoo.co.jp", "search.yahoo.co.jp", "chiebukuro.yahoo.co.jp",
    "auctions.yahoo.co.jp", "shopping.yahoo.co.jp", "news.yahoo.co.jp",
    "map.yahoo.co.jp", "btoptout.yahoo.co.jp", "login.yahoo.co.jp",
    "kisekae.yahoo.co.jp", "s.yimg.jp", "yimg.jp",
    "duckduckgo.com", "duckduckstatic.com",
    "facebook.com", "fb.com", "fbcdn.net",
    "twitter.com", "x.com", "twimg.com",
    "linkedin.com", "t.co", "bit.ly",
    "r.search.yahoo.com", "search.yahoo.com",
    "amazon.com", "amazon.co.uk", "amazon.de",  # often pollute results
    "wikipedia.org", "wikimedia.org",
    "reddit.com", "redd.it",
    "instagram.com", "pinterest.com",
    "tiktok.com", "snapchat.com",
    "cloudflare.com", "akamai.com",
    "w3.org", "schema.org", "opengraph.io",
}

BLOCKED_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".xml", ".gz", ".zip", ".tar", ".rar",
    ".mp4", ".mp3", ".avi", ".mov", ".mkv", ".webm",
    ".swf", ".wav", ".ogg", ".flac",
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "yclid", "utm_id", "utm_name",
    "ref", "referrer", "source", "_ga", "_gid",
}

SIGNAL_EXTENSIONS = {
    ".php", ".asp", ".aspx", ".jsp", ".cfm", ".cgi", ".pl",
    ".do", ".action", ".shtml", ".htm", ".html",
}

SIGNAL_PATH_KEYWORDS = [
    "index.php", "view.php", "item.php", "product.php", "category.php",
    "search.php", "detail.php", "details.php", "article.php", "news.php",
    "download.php", "profile.php", "login.php", "cart.php", "checkout.php",
    "order.php", "admin.php", "show.php", "page.php", "shop.php",
    "store.php", "buy.php", "offer.php", "deal.php",
]


class Engine(Enum):
    GOOGLE = "Google"
    BING = "Bing"
    YAHOO = "Yahoo"
    DUCKDUCKGO = "DuckDuckGo"
    YAHOO_JAPAN = "YahooJapan"
    AOL = "AOL"
    CHROME = "Chrome(Google)"


@dataclass
class Settings:
    concurrency: int = 30       # parallel dork×engine workers
    max_pages: int = 10         # pages per engine per dork
    php_only: bool = False
    require_query: bool = False
    unique_sites_only: bool = False
    proxy_mode: str = "proxyless"
    proxy_protocol: str = "http"
    fast_mode: bool = True
    engines: list = None
    chrome_headless: bool = False

    def __post_init__(self):
        if self.engines is None:
            self.engines = [Engine.BING, Engine.YAHOO, Engine.DUCKDUCKGO, Engine.YAHOO_JAPAN, Engine.AOL]


def read_lines(path):
    if not os.path.exists(path):
        return []
    lines = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            lines.append(s)
    return lines


def append_line(path, line):
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# Matches extensions like .php, .asp, .htm, etc. optionally followed by ?param= at EOL
_DORK_SUFFIX_RE = re.compile(
    r"\s*\.[a-z0-9]{2,6}(?:\d+)?(?:\?[\w_]+=\s*)?$",
    re.IGNORECASE,
)

def dork_to_query(dork: str) -> str:
    """
    Convert a raw dork entry to a clean search engine query.
    Strips trailing .ext?param= style suffixes that come from the dorks.txt format.
    Examples:
        'Membresía VIP .htm?cat='  -> 'Membresía VIP'
        'inurl:index.php?id='      -> 'inurl:index.php?id='  (kept, valid dork)
        'site:example.com'         -> 'site:example.com'     (kept)
    """
    # If the dork has proper operators, leave it alone
    has_operator = bool(re.search(
        r'\b(inurl|intitle|intext|site|filetype|cache|allinurl|allintitle):', dork, re.I
    ))
    if has_operator:
        return dork.strip()
    # Strip trailing .ext or .ext?param=
    cleaned = _DORK_SUFFIX_RE.sub("", dork).strip()
    return cleaned if cleaned else dork.strip()


class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.proxy_type = "proxyless"
        self._index = 0
        self.sources = {
            "http": [
                "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
                "https://www.proxy-list.download/api/v1/get?type=http",
                "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
                "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            ],
            "socks4": [
                "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
                "https://www.proxy-list.download/api/v1/get?type=socks4",
                "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            ],
            "socks5": [
                "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
                "https://www.proxy-list.download/api/v1/get?type=socks5",
                "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            ],
        }

    def clear(self):
        self.proxies = []
        self.proxy_type = "proxyless"
        self._index = 0

    def load_from_file(self, path, protocol):
        if not os.path.exists(path):
            return 0
        lines = read_lines(path)
        self.proxies = [l for l in lines if ":" in l]
        self.proxy_type = protocol
        self._index = 0
        return len(self.proxies)

    async def scrape_online(self, protocol):
        new_proxies = []
        urls = self.sources.get(protocol, self.sources["http"])
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        async with aiohttp.ClientSession(headers=headers) as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                        if r.status == 200:
                            text = await r.text()
                            found = re.findall(r"\d+\.\d+\.\d+\.\d+:\d+", text)
                            new_proxies.extend(found)
                except Exception:
                    continue
        self.proxies = list(set(new_proxies))
        self.proxy_type = protocol
        self._index = 0
        return len(self.proxies)

    async def validate_proxies(self, protocol):
        if not self.proxies:
            return 0
        test_url = "https://www.bing.com/robots.txt"
        timeout = aiohttp.ClientTimeout(total=8)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        valid = []
        sem = asyncio.Semaphore(30)

        async def check(p):
            proxy_url = f"{protocol}://{p}"
            async with sem:
                try:
                    if protocol.startswith("socks"):
                        connector = ProxyConnector.from_url(proxy_url)
                        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as s:
                            async with s.get(test_url, ssl=False) as r:
                                if r.status == 200:
                                    valid.append(p)
                    else:
                        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
                            async with s.get(test_url, proxy=proxy_url, ssl=False) as r:
                                if r.status == 200:
                                    valid.append(p)
                except Exception:
                    pass

        await asyncio.gather(*[check(p) for p in list(self.proxies)])
        self.proxies = valid
        self.proxy_type = protocol
        self._index = 0
        return len(self.proxies)

    def next_proxy(self):
        if not self.proxies:
            return None
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return f"{self.proxy_type}://{proxy}"


class URLStore:
    def __init__(self):
        self._lock = Lock()
        self._urls = set()
        self._domains = set()
        self.unique_site_only = False

    def set_unique_site_only(self, value):
        with self._lock:
            self.unique_site_only = bool(value)

    def add(self, url):
        try:
            parsed = urllib.parse.urlparse(url)
            scheme = (parsed.scheme or "http").lower()
            netloc = parsed.netloc.lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            path = parsed.path or "/"
            path = path.rstrip("/") or "/"
            q = sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
            norm = f"{scheme}://{netloc}{path}" + (f"?{urllib.parse.urlencode(q)}" if q else "")
            norm = norm.rstrip("&").rstrip("?").strip()
            with self._lock:
                if self.unique_site_only:
                    if netloc in self._domains:
                        return False
                    self._domains.add(netloc)
                    self._urls.add(norm)
                    return True
                if norm in self._urls:
                    return False
                self._urls.add(norm)
                return True
        except Exception:
            return False


class URLFilter:
    def __init__(self):
        self.php_only = False
        self.require_query = False

    def is_valid(self, url):
        if not url or not url.startswith("http"):
            return False
        try:
            parsed = urllib.parse.urlparse(url)
            # Must have a real netloc
            netloc = parsed.netloc.lower()
            if not netloc or "." not in netloc:
                return False
            domain = netloc.split(":")[0]
            if domain.startswith("www."):
                domain = domain[4:]
            # Block known bad domains
            for b in BLOCKED_DOMAINS:
                if domain == b or domain.endswith("." + b):
                    return False
            path = (parsed.path or "").lower()
            # Block bad extensions
            ext = os.path.splitext(path.split("?")[0])[1].lower() if "." in path else ""
            if ext in BLOCKED_EXTENSIONS:
                return False
            if self.php_only and not path.endswith(".php"):
                return False
            if self.require_query and not parsed.query:
                return False
            return True
        except Exception:
            return False


class Stats:
    def __init__(self):
        self._lock = Lock()
        self.found = 0
        self.valid = 0
        self.duplicates = 0
        self.errors = 0
        self.retries = 0
        self.dorks_done = 0
        self.total_dorks = 0
        self.current_dork = "N/A"
        self.current_engine = "N/A"
        self.rejected = []

    def set_current(self, dork, engine):
        with self._lock:
            self.current_dork = dork
            self.current_engine = engine

    def add_found(self, n=1):
        with self._lock:
            self.found += n

    def add_valid(self):
        with self._lock:
            self.valid += 1

    def add_duplicate(self):
        with self._lock:
            self.duplicates += 1

    def add_error(self):
        with self._lock:
            self.errors += 1

    def add_retry(self):
        with self._lock:
            self.retries += 1

    def inc_dorks(self):
        with self._lock:
            self.dorks_done += 1

    def snapshot(self):
        with self._lock:
            return {
                "found": self.found,
                "valid": self.valid,
                "dupes": self.duplicates,
                "errors": self.errors,
                "retries": self.retries,
                "dorks_done": self.dorks_done,
                "total": self.total_dorks,
                "dork": self.current_dork,
                "engine": self.current_engine,
            }
            
    def add_rejected(self, url):
        with self._lock:
            if len(self.rejected) < 100:
                self.rejected.append(url)


class Cleaner:
    def clean(self, url):
        try:
            url = (url or "").strip()
            if not url:
                return url
            if url.startswith("//"):
                url = "https:" + url
            url = urllib.parse.unquote(url)
            url = url.split("#")[0]
            # DuckDuckGo redirect
            if "duckduckgo.com/l/?" in url and "uddg=" in url:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                if "uddg" in q:
                    cand = urllib.parse.unquote(q["uddg"][0])
                    if cand.startswith("http"):
                        url = cand
            # Google redirect
            if "google.com/url" in url and "q=" in url:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("q", [])
                if q and q[0].startswith("http"):
                    url = urllib.parse.unquote(q[0])
            # Yahoo redirect - multiple patterns
            if "r.search.yahoo.com" in url or "/RU=" in url:
                m = re.search(r"/RU=([^/]+)/", url)
                if not m:
                    m = re.search(r"RU=([^&\s]+)", url)
                if m:
                    cand = urllib.parse.unquote(m.group(1))
                    if cand.startswith("http"):
                        url = cand
            # Bing redirect (base64 encoded)
            if "bing.com/ck/a" in url and "u=a1" in url:
                m = re.search(r"u=a1([\w%-]+)", url)
                if m:
                    s = m.group(1).replace("-", "+").replace("_", "/")
                    s += "=" * ((4 - len(s) % 4) % 4)
                    try:
                        url = urllib.parse.unquote(base64.b64decode(s).decode("utf-8", "ignore"))
                    except Exception:
                        pass
            # Strip trailing junk
            while url and url[-1] in ".,;:)]}>\\'\"":
                url = url[:-1]
            # Remove tracking params
            pr = urllib.parse.urlparse(url)
            q = urllib.parse.parse_qsl(pr.query, keep_blank_values=True)
            q = [(k, v) for (k, v) in q if k.lower() not in TRACKING_PARAMS]
            new_q = urllib.parse.urlencode(q)
            cleaned = urllib.parse.urlunparse(
                (pr.scheme, pr.netloc, pr.path.rstrip("/") or "/", pr.params, new_q, "")
            )
            return cleaned
        except Exception:
            return url


# ─────────────────────────── Chrome Selenium engine ───────────────────────────

class ChromeScraper:
    """Uses a real Chrome browser via Selenium to search Google and extract URLs."""

    GOOGLE_RESULT_SELECTORS = [
        "div.yuRUbf > a[href]",
        "div.tF2Cxc a[href]",
        "div.g a[href]",
        "h3.LC20lb",          # parent tag is the <a>
        "a[jsname='UWckNb']",
        "div[data-hveid] a[href]",
        ".rc a[href]",
    ]

    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None
        self.cleaner = Cleaner()

    def start(self):
        if self.driver:
            return
        opts = ChromeOptions()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--lang=en-US")
        # Try to use installed chromedriver first, then webdriver-manager
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=opts)
        except Exception:
            self.driver = webdriver.Chrome(options=opts)
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

    def stop(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _dismiss_consent(self):
        """Try to click any cookie/consent dialog."""
        for sel in ["button#L2AGLb", "button[aria-label*='Accept']", "button[id*='accept']",
                    "button[id*='agree']", "#onetrust-accept-btn-handler"]:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                btn.click()
                time.sleep(0.8)
                return
            except Exception:
                pass

    def search(self, query, max_pages=3):
        """Search Google for `query`, iterate pages, return list of URLs."""
        if not SELENIUM_OK:
            return []
        self.start()
        all_links = []
        cleaner = Cleaner()
        for page in range(max_pages):
            start = page * 10
            encoded = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded}&num=10&start={start}&hl=en"
            try:
                self.driver.get(url)
                time.sleep(random.uniform(2.0, 3.5))
                self._dismiss_consent()
                # Check for CAPTCHA
                pg = self.driver.page_source.lower()
                if "detected unusual traffic" in pg or "captcha" in pg or "sorry" in pg and "google" in pg:
                    print(Fore.YELLOW + f"  [Chrome] CAPTCHA detected on page {page+1}, waiting 15s…")
                    time.sleep(15)
                    continue
                # Extract links
                links = self._extract_links()
                if not links:
                    break
                for lnk in links:
                    cleaned = cleaner.clean(lnk)
                    if cleaned and cleaned.startswith("http"):
                        all_links.append(cleaned)
                if page < max_pages - 1:
                    time.sleep(random.uniform(1.5, 3.0))
            except WebDriverException as e:
                print(Fore.RED + f"  [Chrome] WebDriver error: {e}")
                break
        return all_links

    def _extract_links(self):
        links = []
        src = self.driver.page_source
        soup = BeautifulSoup(src, "html.parser")
        # Primary selectors
        for sel in self.GOOGLE_RESULT_SELECTORS:
            try:
                elems = soup.select(sel)
                for e in elems:
                    href = e.get("href") if e.name == "a" else None
                    if not href and e.name != "a":
                        parent = e.find_parent("a")
                        if parent:
                            href = parent.get("href")
                    if href and href.startswith("http") and "google.com" not in href:
                        links.append(href)
            except Exception:
                pass
        # Regex fallback
        raw = re.findall(r'"(https?://(?!www\.google\.com)[^"<>\s]{10,})"', src)
        links += raw
        # Deduplicate
        seen = set()
        result = []
        for l in links:
            if l not in seen:
                seen.add(l)
                result.append(l)
        return result


# ─────────────────────────── HTTP Scraper ─────────────────────────────────────

class Scraper:
    def __init__(self, settings, proxy_mgr, url_filter, store, stats):
        self.settings = settings
        self.proxy_mgr = proxy_mgr
        self.url_filter = url_filter
        self.store = store
        self.stats = stats
        self.cleaner = Cleaner()
        self.file_lock = asyncio.Lock()
        self.session = None
        self.engine_cooldown = {e: 0 for e in Engine}
        self.cooldown_lock = Lock()
        self.chrome = None

    def _now(self):
        return time.time()

    async def _wait_cooldown(self, engine):
        with self.cooldown_lock:
            until = self.engine_cooldown.get(engine, 0)
        now = self._now()
        if until > now:
            await asyncio.sleep(until - now + random.uniform(0.2, 0.8))

    def _set_cooldown(self, engine, seconds):
        until = self._now() + seconds
        with self.cooldown_lock:
            self.engine_cooldown[engine] = max(self.engine_cooldown.get(engine, 0), until)

    async def _pre_request_delay(self):
        min_s, max_s = (0.5, 1.2) if self.settings.fast_mode else (1.2, 2.5)
        await asyncio.sleep(random.uniform(min_s, max_s))

    def _is_blocked_html(self, engine, html):
        text = (html or "").lower()
        if engine == Engine.GOOGLE:
            return "unusual traffic" in text or ("sorry" in text and "google" in text)
        if engine == Engine.BING:
            return "access denied" in text or "unusual traffic" in text or ("captcha" in text and "bing" in text)
        if engine == Engine.YAHOO:
            return (
                "consent.yahoo.com" in text
                or "guce.yahoo.com" in text
                or "are you a robot" in text
                or "sign in to confirm" in text
            )
        if engine == Engine.YAHOO_JAPAN:
            return "are you a robot" in text or "denied" in text
        if engine == Engine.AOL:
            return "captcha" in text or "are you a robot" in text or "guce.aol.com" in text
        if engine == Engine.DUCKDUCKGO:
            return "too many requests" in text or "rate limit" in text
        return False

    # ----------------------- Per-engine link extractors -----------------------

    def _extract_bing_links(self, html, soup):
        links = []
        # Primary selector (2025-2026 Bing layout)
        for sel in [
            "li.b_algo h2 a[href]",
            "li.b_algo .b_title a[href]",
            "li.b_algo a.tilk[href]",
            "#b_results li.b_algo a[href]",
            "div.b_caption a[href]",
            "div.b_algoheader a[href]",
            "h2 a[href]",
        ]:
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "bing.com" not in href:
                    links.append(href)
        # Regex fallback - grab all hrefs from result items
        if len(links) < 3:
            raw = re.findall(r'href="(https?://(?!.*bing\.com)[^"<>\s]{10,})"', html)
            links += raw
        return links

    def _extract_yahoo_links(self, html, soup):
        candidates = []
        # data-* attributes (most reliable)
        for a in soup.select("a[data-ru], a[data-rurl], a[data-legacyurl]"):
            for attr in ("data-ru", "data-rurl", "data-legacyurl"):
                v = a.get(attr)
                if v and v.startswith("http"):
                    candidates.append(urllib.parse.unquote(v))
        # 2026 Yahoo layout selectors
        for sel in [
            "div#web ol li div.compTitle a[href]",
            "div.algo-sr a[href]",
            "h3.title a[href]",
            "div.Sr a[href]",
            "li.algo div.compTitle a[href]",
            "li.algo h3 a[href]",
            "div#web a[href]",
        ]:
            for a in soup.select(sel):
                href = a.get("href")
                if href:
                    candidates.append(href)
        # Regex: pull RU= encoded URLs
        for m in re.finditer(r"/RU=([^/]+)/", html):
            decoded = urllib.parse.unquote(m.group(1))
            if decoded.startswith("http"):
                candidates.append(decoded)
        for m in re.finditer(r'data-ru="([^"]+)"', html, re.I):
            v = urllib.parse.unquote(m.group(1))
            if v.startswith("http"):
                candidates.append(v)
        # Normalize
        seen = set()
        result = []
        for url in candidates:
            u = urllib.parse.unquote((url or "").strip())
            if not u:
                continue
            if u.startswith("//"):
                u = "https:" + u
            if not u.startswith("http"):
                continue
            # Skip Yahoo internal
            if "yahoo.com" in u.lower() and "r.search.yahoo" not in u.lower():
                pass  # keep - might be real yahoo result
            if u not in seen:
                seen.add(u)
                result.append(u)
        return result

    def _extract_ddg_links(self, html, soup):
        links = []
        # html.duckduckgo.com selectors
        for sel in [
            "a.result__a[href]",
            "article[data-testid='result'] a[href]",
            "div.result__body a.result__a[href]",
            "h2 a.result__a[href]",
        ]:
            for a in soup.select(sel):
                href = a.get("href")
                if href:
                    if href.startswith("//"):
                        href = "https:" + href
                    # DDG uses redirect /l/?uddg=...
                    if "duckduckgo.com/l/?" in href or "uddg=" in href:
                        m = re.search(r"uddg=([^&]+)", href)
                        if m:
                            href = urllib.parse.unquote(m.group(1))
                    if href.startswith("http") and "duckduckgo.com" not in href:
                        links.append(href)
        # Regex fallback
        if len(links) < 3:
            for m in re.finditer(r"uddg=(https?[^&\"<>\s]+)", html):
                links.append(urllib.parse.unquote(m.group(1)))
            raw = re.findall(r'"(https?://(?!.*duckduckgo\.com)[^"<>\s]{10,})"', html)
            links += raw
        return links

    def _extract_yahoo_jp_links(self, html, soup):
        """Extract only actual search result URLs from Yahoo Japan HTML."""
        links = []
        # Yahoo Japan wraps results in div.sw-Card or similar wrappers.
        # We look for the outer anchor that points to an external site.
        # The result title anchors are inside div.sw-Card__title or div.ContentWrapper
        for a in soup.select("div.sw-Card__title a[href], div.ContentWrapper a[href], div.swof_title a[href], h3.sw-Card__title a[href]"):
            href = a.get("href", "")
            if href.startswith("http") and "yahoo.co.jp" not in href and "yimg.jp" not in href:
                links.append(href)
        # Regex fallback: grab only external URLs not under yahoo.co.jp domains
        if len(links) < 3:
            raw = re.findall(
                r'href="(https?://(?!(?:[^/]*\.)?yahoo\.co\.jp)(?!(?:[^/]*\.)?yimg\.jp)[^"<>\s]{10,})"',
                html
            )
            # Only keep links that look like real pages (have a path or query)
            for url in raw:
                try:
                    parsed = urllib.parse.urlparse(url)
                    if parsed.netloc and (parsed.path.strip("/") or parsed.query):
                        links.append(url)
                except Exception:
                    pass
        return links
        
    def _extract_aol_links(self, html, soup):
        links = []
        for sel in [
            "h3.title a[href]",
            "div.compTitle a[href]",
            "a.ac-algo[href]",
            "div.algo-sr a[href]"
        ]:
            for a in soup.select(sel):
                href = a.get("href")
                if href:
                    # AOL sometimes routes through RU=
                    m = re.search(r"RU=([^/]+)/", href)
                    if m:
                        href = urllib.parse.unquote(m.group(1))
                    if href.startswith("http") and "aol.com" not in href:
                        links.append(href)
        return links

    def _extract_google_links(self, html, soup):
        links = []
        for sel in [
            "div.yuRUbf a[href]",
            "div.tF2Cxc a[href]",
            "div.g div.r a[href]",
            "a[jsname='UWckNb'][href]",
            "a[ping][href]",
        ]:
            for a in soup.select(sel):
                href = a.get("href")
                if href and href.startswith("http") and "google.com" not in href:
                    links.append(href)
        # /url?q= style redirects
        for a in soup.select("a[href^='/url?']"):
            href = a.get("href", "")
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("q", [])
            if q and q[0].startswith("http"):
                links.append(q[0])
        return links

    def extract_links(self, html, engine):
        soup = BeautifulSoup(html, "html.parser")
        if engine == Engine.GOOGLE:
            links = self._extract_google_links(html, soup)
        elif engine == Engine.BING:
            links = self._extract_bing_links(html, soup)
        elif engine == Engine.YAHOO:
            links = self._extract_yahoo_links(html, soup)
        elif engine == Engine.YAHOO_JAPAN:
            links = self._extract_yahoo_jp_links(html, soup)
        elif engine == Engine.AOL:
            links = self._extract_aol_links(html, soup)
        elif engine == Engine.DUCKDUCKGO:
            links = self._extract_ddg_links(html, soup)
        else:
            links = []

        # Normalize
        links = [self._normalize_href(l, engine) for l in links]
        links = [l for l in links if l and l.startswith("http")]
        # Regex fallback if still very few results
        if len(links) < 3:
            extra = re.findall(r"https?://[^\s\"'<>]+", html)
            extra = [l for l in extra if self._signal_candidate(l)
                     and "google.com" not in l and "bing.com" not in l
                     and "yahoo.com" not in l and "duckduckgo.com" not in l
                     and "yahoo.co.jp" not in l and "yimg.jp" not in l]
            links += extra
        return list(dict.fromkeys([l for l in links if l]))

    def _normalize_href(self, href, engine):
        if not href:
            return None
        href = href.strip()
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("/"):
            bases = {
                Engine.DUCKDUCKGO: "https://duckduckgo.com",
                Engine.GOOGLE: "https://www.google.com",
                Engine.BING: "https://www.bing.com",
                Engine.YAHOO: "https://search.yahoo.com",
                Engine.YAHOO_JAPAN: "https://search.yahoo.co.jp",
                Engine.AOL: "https://search.aol.com",
            }
            href = bases.get(engine, "") + href
        return href

    def _signal_candidate(self, url):
        try:
            parsed = urllib.parse.urlparse(url)
            path = (parsed.path or "").lower()
            if parsed.query:
                return True
            ext = os.path.splitext(path)[1].lower()
            if ext in SIGNAL_EXTENSIONS:
                return True
            if any(k in path for k in SIGNAL_PATH_KEYWORDS):
                return True
            return False
        except Exception:
            return False

    def _extract_requirements(self, dork):
        """Extract inurl: and filetype: constraints — only from proper dork operators."""
        tokens = []
        tokens += re.findall(r'inurl:"([^"]+)"', dork, re.I)
        tokens += re.findall(r"inurl:([^\s\"]+)", dork, re.I)
        tokens = [t.strip().strip("'").strip('"') for t in tokens if t]
        # Only extract filetype when using proper filetype: operator
        filetypes = re.findall(r"filetype:([^\s\"]+)", dork, re.I)
        filetypes = [f.strip().lower().lstrip(".") for f in filetypes if f]
        return tokens, filetypes

    def _matches_requirements(self, url, tokens, filetypes):
        if tokens:
            low = url.lower()
            if not any(t.lower() in low for t in tokens):
                return False
        if filetypes:
            path = urllib.parse.urlparse(url).path.lower()
            if not any(path.endswith("." + f) for f in filetypes):
                return False
        return True

    def build_url(self, engine, query, page):
        # Auto-clean dork before encoding (strips .ext?param= suffixes)
        clean_q = dork_to_query(query)
        encoded = urllib.parse.quote_plus(clean_q)
        if engine == Engine.GOOGLE:
            return f"https://www.google.com/search?q={encoded}&num=10&start={page * 10}&hl=en"
        if engine == Engine.BING:
            return f"https://www.bing.com/search?q={encoded}&first={page * 10 + 1}&setlang=en"
        if engine == Engine.YAHOO:
            return f"https://search.yahoo.com/search?p={encoded}&b={page * 10 + 1}&vl=lang_en"
        if engine == Engine.YAHOO_JAPAN:
            return f"https://search.yahoo.co.jp/search?p={encoded}&b={page * 10 + 1}"
        if engine == Engine.AOL:
            return f"https://search.aol.com/aol/search?q={encoded}&b={page * 10 + 1}"
        if engine == Engine.DUCKDUCKGO:
            base = f"https://html.duckduckgo.com/html/?q={encoded}"
            if page > 0:
                base += f"&s={page * 30}&dc={page * 30 + 1}&v=l&o=json&api=%2Fd.js"
            return base
        return None

    async def open(self):
        if not self.session or self.session.closed:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            }
            timeout = aiohttp.ClientTimeout(total=20)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        if self.chrome:
            self.chrome.stop()

    async def fetch(self, url, proxy_url, engine):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1"
        }
        
        if engine == Engine.BING:
            headers["Cookie"] = "SRCHD=AF=NOFORM; SRCHUID=V=2&GUID=152E520A9F9C4A2DB1DDB14AE3B4706A; SRCHUSR=DOB=20230214; _EDGE_V=1; MUID=38D5B0F7604B6D8A2ACCBE3F616C6C26"
            headers["Referer"] = "https://www.bing.com/"
        elif engine == Engine.YAHOO:
            headers["Cookie"] = "A1=d=AQABBPYdO2QCEKjVXYo8cM91_E08M2X8J0QFEgEBAQHnO2QYZwAAAAAA_eMAAAcI9h07ZGX8J0Q&S=AQAAAhw4Uj7_H7-7C00wF43Poy8;"
            headers["Referer"] = "https://search.yahoo.com/"
        elif engine == Engine.YAHOO_JAPAN:
            headers["Referer"] = "https://www.yahoo.co.jp/"
        elif engine == Engine.AOL:
            headers["Referer"] = "https://www.aol.com/"
            
        # DuckDuckGo needs POST for pagination
        use_post = engine == Engine.DUCKDUCKGO and "s=" in url
        for attempt in range(3):
            try:
                await self._wait_cooldown(engine)
                await self._pre_request_delay()
                if proxy_url and proxy_url.startswith("socks"):
                    connector = ProxyConnector.from_url(proxy_url)
                    timeout = aiohttp.ClientTimeout(total=20)
                    async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as s:
                        req = s.post(url, ssl=False) if use_post else s.get(url, ssl=False)
                        async with req as r:
                            if r.status == 200:
                                text = await r.text()
                                if self._is_blocked_html(engine, text):
                                    self.stats.add_retry()
                                    self._set_cooldown(engine, random.uniform(15, 30))
                                    return None
                                return text
                            if r.status in (429, 403, 503):
                                self.stats.add_retry()
                                self._set_cooldown(engine, random.uniform(15, 40))
                                await asyncio.sleep(random.uniform(2.0, 4.0) * (attempt + 1))
                                continue
                            return None
                else:
                    await self.open()
                    proxy = proxy_url if proxy_url and proxy_url.startswith("http") else None
                    req = self.session.post(url, proxy=proxy, headers=headers, ssl=False) if use_post else self.session.get(url, proxy=proxy, headers=headers, ssl=False)
                    async with req as r:
                        if r.status == 200:
                            text = await r.text()
                            if self._is_blocked_html(engine, text):
                                self.stats.add_retry()
                                self._set_cooldown(engine, random.uniform(15, 30))
                                return None
                            return text
                        if r.status in (202, 429, 403, 503):
                            self.stats.add_retry()
                            self._set_cooldown(engine, random.uniform(15, 40))
                            await asyncio.sleep(random.uniform(2.0, 4.0) * (attempt + 1))
                            continue
                        print(f"[{engine.name}] Unhandled status {r.status} for {url}")
                        return None
            except Exception as e:
                print(f"[{engine.name}] ERROR fetching {url}: {e!r}")
                self.stats.add_error()
                self._set_cooldown(engine, random.uniform(2, 6))
                await asyncio.sleep(random.uniform(0.5, 1.5) * (attempt + 1))
        return None

    async def write_url(self, path, url):
        async with self.file_lock:
            append_line(path, url)

    async def scrape_chrome(self, dork, out_file):
        """Use Chrome (Selenium) to search Google and extract URLs."""
        if not SELENIUM_OK:
            print(Fore.RED + "  [!] Selenium not installed. Run: pip install selenium webdriver-manager")
            return
        if not self.chrome:
            self.chrome = ChromeScraper(headless=self.settings.chrome_headless)
        loop = asyncio.get_event_loop()
        raw_links = await loop.run_in_executor(
            None, self.chrome.search, dork, self.settings.max_pages
        )
        tokens, filetypes = self._extract_requirements(dork)
        self.stats.add_found(len(raw_links))
        for link in raw_links:
            cleaned = self.cleaner.clean(link)
            if not self._matches_requirements(cleaned, tokens, filetypes):
                continue
            if self.url_filter.is_valid(cleaned):
                if self.store.add(cleaned):
                    self.stats.add_valid()
                    await self.write_url(out_file, cleaned)
                else:
                    self.stats.add_duplicate()
            else:
                self.stats.add_rejected(cleaned)

    async def _scrape_ddgs(self, dork, tokens, filetypes, out_file):
        """Use duckduckgo_search library directly for maximum speed and yield."""
        loop = asyncio.get_event_loop()
        def _fetch_ddgs():
            try:
                limit = self.settings.max_pages * 12
                results = []
                proxy_dict = None
                if self.settings.proxy_mode != "proxyless":
                    p = self.proxy_mgr.next_proxy()
                    if p:
                        proxy_dict = {"http": p, "https": p}
                try:
                    with DDGS(proxies=proxy_dict) as ddgs:
                        for r in ddgs.text(dork, max_results=limit):
                            results.append(r.get("href"))
                except Exception:
                    # fallback without proxies if proxy failed
                    with DDGS() as ddgs:
                        for r in ddgs.text(dork, max_results=limit):
                            results.append(r.get("href"))
                return results
            except Exception:
                return []
        
        raw_links = await loop.run_in_executor(None, _fetch_ddgs)
        if not raw_links:
            return
            
        self.stats.add_found(len(raw_links))
        for link in raw_links:
            if not link:
                continue
            cleaned = self.cleaner.clean(link)
            if not self._matches_requirements(cleaned, tokens, filetypes):
                continue
            if self.url_filter.is_valid(cleaned):
                if self.store.add(cleaned):
                    self.stats.add_valid()
                    await self.write_url(out_file, cleaned)
                else:
                    self.stats.add_duplicate()
            else:
                self.stats.add_rejected(cleaned)

    async def scrape(self, dork, engine, out_file):
        """Scrape all pages for a dork/engine pair CONCURRENTLY."""
        if engine == Engine.CHROME:
            await self.scrape_chrome(dork, out_file)
            return

        self.stats.set_current(dork, engine.value)
        tokens, filetypes = self._extract_requirements(dork)

        if engine == Engine.DUCKDUCKGO:
            await self._scrape_ddgs(dork, tokens, filetypes, out_file)
            return

        # ── Build the list of page URLs up-front ───────────────────────────
        page_urls = []
        for page in range(self.settings.max_pages):
            url = self.build_url(engine, dork, page)
            if url:
                page_urls.append((page, url))

        if not page_urls:
            return

        # ── Fetch pages concurrently with a small per-engine semaphore ─────
        # Use 3 concurrent fetches per engine so we don't hammer one server.
        page_sem = asyncio.Semaphore(3)

        async def fetch_page(page, url):
            async with page_sem:
                proxy_url = None
                if self.settings.proxy_mode != "proxyless":
                    proxy_url = self.proxy_mgr.next_proxy()
                # Small jitter between page requests to avoid rate limits
                await asyncio.sleep(random.uniform(0.1, 0.5) * page)
                return page, await self.fetch(url, proxy_url, engine)

        results = await asyncio.gather(*[fetch_page(p, u) for p, u in page_urls])

        # ── Process results in page order ──────────────────────────────────
        got_any = False
        for page, html in sorted(results, key=lambda x: x[0]):
            if not html:
                if page == 0:
                    break  # blocked / empty on page 1 → give up
                continue
            raw_links = self.extract_links(html, engine)
            if not raw_links:
                continue
            got_any = True
            self.stats.add_found(len(raw_links))
            for link in raw_links:
                cleaned = self.cleaner.clean(link)
                if not self._matches_requirements(cleaned, tokens, filetypes):
                    continue
                if self.url_filter.is_valid(cleaned):
                    if self.store.add(cleaned):
                        self.stats.add_valid()
                        await self.write_url(out_file, cleaned)
                    else:
                        self.stats.add_duplicate()
                else:
                    self.stats.add_rejected(cleaned)


class App:
    def __init__(self):
        self.settings = Settings()
        self.proxy_mgr = ProxyManager()
        self.url_filter = URLFilter()
        self.stats = Stats()
        self.store = URLStore()
        self.store.set_unique_site_only(self.settings.unique_sites_only)
        self.url_filter.php_only = self.settings.php_only
        self.url_filter.require_query = self.settings.require_query
        self.scraper = Scraper(self.settings, self.proxy_mgr, self.url_filter, self.store, self.stats)

    def header(self):
        os.system("cls" if os.name == "nt" else "clear")
        selenium_status = (Fore.GREEN + "✓") if SELENIUM_OK else (Fore.RED + "✗")
        print(Fore.CYAN + Style.BRIGHT + "AKAZA DORK PARSER v8.0" + Style.RESET_ALL)
        print(Fore.LIGHTBLACK_EX + f"  Selenium/Chrome: {selenium_status}" + Style.RESET_ALL)
        print(Fore.LIGHTBLACK_EX + "-" * 70 + Style.RESET_ALL)

    def menu(self, title, options):
        while True:
            self.header()
            print(Fore.YELLOW + title + Style.RESET_ALL)
            for k, v in options.items():
                print(f"  [{k}] {v}")
            choice = input("> ").strip()
            if choice in options:
                return choice

    async def proxy_flow(self):
        while True:
            total = len(self.proxy_mgr.proxies)
            choice = self.menu(
                f"Proxy Management  [type={self.proxy_mgr.proxy_type} | count={total}]",
                {
                    "1": f"Scrape online proxies ({self.settings.proxy_protocol})",
                    "2": f"Load from file ({os.path.basename(PROXIES_FILE)})",
                    "3": "Validate loaded proxies",
                    "4": "Clear proxies",
                    "0": "Back",
                },
            )
            if choice == "1":
                print("Scraping…")
                count = await self.proxy_mgr.scrape_online(self.settings.proxy_protocol)
                print(f"Scraped {count} proxies")
                input("Press Enter…")
            elif choice == "2":
                pr = input("Protocol (http/socks4/socks5): ").strip().lower() or self.settings.proxy_protocol
                if pr in ("http", "socks4", "socks5"):
                    self.settings.proxy_protocol = pr
                count = self.proxy_mgr.load_from_file(PROXIES_FILE, self.settings.proxy_protocol)
                print(f"Loaded {count} proxies")
                input("Press Enter…")
            elif choice == "3":
                print("Validating (this may take a while)…")
                count = await self.proxy_mgr.validate_proxies(self.settings.proxy_protocol)
                print(f"{count} valid proxies remain")
                input("Press Enter…")
            elif choice == "4":
                self.proxy_mgr.clear()
                print("Cleared.")
                input("Press Enter…")
            else:
                return

    def settings_flow(self):
        chrome_status = "✓" if SELENIUM_OK else "✗ (pip install selenium webdriver-manager)"
        choice = self.menu(
            "Settings",
            {
                "1": f"Concurrency: {self.settings.concurrency}",
                "2": f"Max Pages: {self.settings.max_pages}",
                "3": f"PHP-only: {'ON' if self.settings.php_only else 'OFF'}",
                "4": f"SQLi Mode (Require ?param=): {'ON' if self.settings.require_query else 'OFF'}",
                "5": f"Unique Sites Only: {'ON' if self.settings.unique_sites_only else 'OFF'}",
                "6": f"Engines: {', '.join([e.name for e in self.settings.engines])}",
                "7": f"Proxy Mode: {self.settings.proxy_mode} ({self.settings.proxy_protocol})",
                "8": f"Fast Mode: {'ON' if self.settings.fast_mode else 'OFF'}",
                "9": f"Chrome Headless: {'ON' if self.settings.chrome_headless else 'OFF'} [{chrome_status}]",
                "0": "Back",
            },
        )
        if choice == "1":
            val = input("New concurrency (1-200): ").strip()
            if val.isdigit():
                self.settings.concurrency = max(1, min(200, int(val)))
        elif choice == "2":
            val = input("Max pages (1-50): ").strip()
            if val.isdigit():
                self.settings.max_pages = max(1, min(50, int(val)))
        elif choice == "3":
            self.settings.php_only = not self.settings.php_only
            self.url_filter.php_only = self.settings.php_only
        elif choice == "4":
            self.settings.require_query = not self.settings.require_query
            self.url_filter.require_query = self.settings.require_query
        elif choice == "5":
            self.settings.unique_sites_only = not self.settings.unique_sites_only
            self.store.set_unique_site_only(self.settings.unique_sites_only)
        elif choice == "6":
            print("Available: google, bing, yahoo, duck, chrome")
            s = input("Engines (comma separated): ").strip().lower()
            mapping = {
                "google": Engine.GOOGLE,
                "bing": Engine.BING,
                "yahoo": Engine.YAHOO,
                "duck": Engine.DUCKDUCKGO,
                "duckduckgo": Engine.DUCKDUCKGO,
                "chrome": Engine.CHROME,
            }
            chosen = [mapping[p.strip()] for p in s.split(",") if p.strip() in mapping]
            if chosen:
                self.settings.engines = chosen
        elif choice == "7":
            mode = input("Mode (proxyless/file/online): ").strip().lower() or self.settings.proxy_mode
            if mode in ("proxyless", "file", "online"):
                self.settings.proxy_mode = mode
            if self.settings.proxy_mode != "proxyless":
                pr = input("Protocol (http/socks4/socks5): ").strip().lower() or self.settings.proxy_protocol
                if pr in ("http", "socks4", "socks5"):
                    self.settings.proxy_protocol = pr
        elif choice == "8":
            self.settings.fast_mode = not self.settings.fast_mode
        elif choice == "9":
            if not SELENIUM_OK:
                print(Fore.RED + "Selenium not installed. Run: pip install selenium webdriver-manager")
                input("Press Enter…")
                return
            self.settings.chrome_headless = not self.settings.chrome_headless
        elif choice == "0":
            return
        self.settings_flow()

    async def dashboard(self):
        start = time.time()
        while self.stats.dorks_done < self.stats.total_dorks:
            s = self.stats.snapshot()
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            self.header()
            print(Fore.CYAN + f"  Time: {mins:02d}:{secs:02d}  |  Dorks: {s['dorks_done']}/{s['total']}")
            print(Fore.GREEN + f"  Engine: {s['engine']:<20}  Dork: {str(s['dork'])[:55]}")
            print()
            print(
                Fore.WHITE + f"  Found: {Fore.YELLOW}{s['found']}"
                + Fore.WHITE + f"  Valid: {Fore.GREEN}{s['valid']}"
                + Fore.WHITE + f"  Dupes: {Fore.LIGHTBLACK_EX}{s['dupes']}"
                + Fore.WHITE + f"  Errors: {Fore.RED}{s['errors']}"
                + Fore.WHITE + f"  Retries: {Fore.MAGENTA}{s['retries']}"
            )
            await asyncio.sleep(1)

    async def run_parser(self):
        self.header()
        dorks = read_lines(DORKS_FILE)
        if not dorks:
            print(Fore.RED + "No dorks found in dorks.txt")
            input("Press Enter…")
            return
        os.makedirs(RESULTS_DIR, exist_ok=True)
        out_file = os.path.join(RESULTS_DIR, f"urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        engines = list(self.settings.engines)
        self.stats.total_dorks = len(dorks) * len(engines)

        # Try to load proxies from file if in proxyless mode and file has content
        if self.settings.proxy_mode == "proxyless":
            proxy_candidates = read_lines(PROXIES_FILE)
            if proxy_candidates:
                self.settings.proxy_mode = "file"

        try:
            await self.scraper.open()
            if self.settings.proxy_mode == "file":
                cnt = self.proxy_mgr.load_from_file(PROXIES_FILE, self.settings.proxy_protocol)
                if cnt:
                    print(f"Loaded {cnt} proxies, validating…")
                    valid = await self.proxy_mgr.validate_proxies(self.settings.proxy_protocol)
                    print(f"{valid} valid proxies")
                else:
                    self.settings.proxy_mode = "proxyless"
            elif self.settings.proxy_mode == "online":
                cnt = await self.proxy_mgr.scrape_online(self.settings.proxy_protocol)
                print(f"Scraped {cnt} proxies, validating…")
                await self.proxy_mgr.validate_proxies(self.settings.proxy_protocol)

            if self.settings.proxy_mode != "proxyless" and not self.proxy_mgr.proxies:
                self.settings.proxy_mode = "proxyless"
                print(Fore.YELLOW + "No valid proxies found, running proxyless.")
                await asyncio.sleep(1)

            db_task = asyncio.create_task(self.dashboard())
            sem = asyncio.Semaphore(self.settings.concurrency)

            async def worker(dork, engine):
                async with sem:
                    self.stats.set_current(dork, engine.value)
                    await self.scraper.scrape(dork, engine, out_file)
                    self.stats.inc_dorks()

            # Chrome engine must run serially (one browser, no real concurrency)
            chrome_engines = [e for e in engines if e == Engine.CHROME]
            other_engines = [e for e in engines if e != Engine.CHROME]

            tasks = []
            for d in dorks:
                for e in other_engines:
                    tasks.append(asyncio.create_task(worker(d, e)))
            if tasks:
                await asyncio.gather(*tasks)

            # Chrome: serial
            if chrome_engines:
                for d in dorks:
                    self.stats.set_current(d, Engine.CHROME.value)
                    await self.scraper.scrape(d, Engine.CHROME, out_file)
                    self.stats.inc_dorks()

            db_task.cancel()
        finally:
            await self.scraper.close()

        self.header()
        s = self.stats.snapshot()
        print(Fore.GREEN + f"  Done!  Valid URLs: {s['valid']}  |  File: {os.path.basename(out_file)}")
        print(Fore.LIGHTBLACK_EX + f"  Path: {out_file}")
        input("\nPress Enter to continue…")

    def main(self):
        while True:
            choice = self.menu(
                "Main Menu",
                {
                    "1": "Start Parser",
                    "2": "Proxy Management",
                    "3": "Settings",
                    "0": "Exit",
                },
            )
            if choice == "1":
                asyncio.run(self.run_parser())
            elif choice == "2":
                asyncio.run(self.proxy_flow())
            elif choice == "3":
                self.settings_flow()
            elif choice == "0":
                sys.exit(0)


if __name__ == "__main__":
    App().main()
