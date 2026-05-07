"""Proxy manager with rotation, ban-list, sticky sessions, and online scraping."""

from __future__ import annotations

import asyncio
import random
import re
import time
from threading import Lock

import aiohttp

from .config import USER_AGENTS, read_lines

# Free proxy sources by protocol.
_SOURCES: dict[str, list[str]] = {
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

# Residential gateway hostnames — these are sticky-session gateways that
# should NOT be banned/rotated.  User provides them as user:pass@host:port.
_RESI_PATTERNS = re.compile(
    r"(resi|residential|rotating|gate|proxy\.net|proxy\.com|oxylabs"
    r"|smartproxy|brightdata|luminati|packetstream|storm|geosurf"
    r"|shifter|netnut|iproyal|webshare)",
    re.IGNORECASE,
)

_BAN_TTL = 300  # seconds


class ProxyManager:
    """Thread-safe proxy pool with banning + sticky detection."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._proxies: list[str] = []
        self._protocol: str = "http"
        self._idx: int = 0
        self._banned: dict[str, float] = {}  # proxy_url -> ban_until
        self._is_residential: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def protocol(self) -> str:
        with self._lock:
            return self._protocol

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._proxies)

    @property
    def is_residential(self) -> bool:
        with self._lock:
            return self._is_residential

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def clear(self) -> None:
        with self._lock:
            self._proxies.clear()
            self._idx = 0
            self._banned.clear()
            self._is_residential = False

    def load_from_file(self, path: str, protocol: str = "http") -> int:
        lines = read_lines(path)
        proxies = [p for p in lines if ":" in p]
        with self._lock:
            self._proxies = proxies
            self._protocol = protocol
            self._idx = 0
            self._is_residential = any(_RESI_PATTERNS.search(p) for p in proxies)
        return len(proxies)

    def load_from_list(self, proxies: list[str], protocol: str = "http") -> int:
        with self._lock:
            self._proxies = list(proxies)
            self._protocol = protocol
            self._idx = 0
            self._is_residential = any(_RESI_PATTERNS.search(p) for p in proxies)
        return len(self._proxies)

    # ------------------------------------------------------------------
    # Online scraping
    # ------------------------------------------------------------------

    async def scrape_online(self, protocol: str = "http") -> int:
        urls = _SOURCES.get(protocol, _SOURCES["http"])
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        new: list[str] = []
        async with aiohttp.ClientSession(headers=headers) as sess:
            for url in urls:
                try:
                    async with sess.get(
                        url, timeout=aiohttp.ClientTimeout(total=12)
                    ) as r:
                        if r.status == 200:
                            text = await r.text()
                            new.extend(re.findall(r"\d+\.\d+\.\d+\.\d+:\d+", text))
                except Exception:
                    continue
        with self._lock:
            self._proxies = list(set(new))
            self._protocol = protocol
            self._idx = 0
            self._is_residential = False
        return len(self._proxies)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate(self, protocol: str | None = None, *, max_concurrent: int = 40) -> int:
        proto = protocol or self.protocol
        with self._lock:
            to_test = list(self._proxies)
        if not to_test:
            return 0

        test_url = "https://httpbin.org/ip"
        timeout = aiohttp.ClientTimeout(total=8)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        valid: list[str] = []
        sem = asyncio.Semaphore(max_concurrent)

        async def _check(p: str) -> None:
            proxy_url = f"{proto}://{p}"
            async with sem:
                try:
                    if proto.startswith("socks"):
                        from aiohttp_socks import ProxyConnector
                        connector = ProxyConnector.from_url(proxy_url)
                        async with aiohttp.ClientSession(
                            connector=connector, timeout=timeout, headers=headers
                        ) as s:
                            async with s.get(test_url, ssl=False) as r:
                                if r.status == 200:
                                    valid.append(p)
                    else:
                        async with aiohttp.ClientSession(
                            timeout=timeout, headers=headers
                        ) as s:
                            async with s.get(
                                test_url, proxy=proxy_url, ssl=False
                            ) as r:
                                if r.status == 200:
                                    valid.append(p)
                except Exception:
                    pass

        await asyncio.gather(*[_check(p) for p in to_test])
        with self._lock:
            self._proxies = valid
            self._protocol = proto
            self._idx = 0
        return len(valid)

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def next_proxy(self) -> str | None:
        """Return the next proxy URL (``protocol://host:port``) or ``None``."""
        with self._lock:
            if not self._proxies:
                return None
            now = time.time()
            # Try up to len(pool) proxies to find an unbanned one.
            for _ in range(len(self._proxies)):
                raw = self._proxies[self._idx % len(self._proxies)]
                self._idx += 1
                full = self._format(raw)
                if self._banned.get(full, 0) <= now:
                    return full
            # All banned → return one anyway (least recently banned).
            raw = random.choice(self._proxies)
            return self._format(raw)

    def ban(self, proxy_url: str, seconds: float = _BAN_TTL) -> None:
        """Temporarily ban a proxy after a hard failure."""
        if self._is_residential:
            return  # never ban residential gateways
        with self._lock:
            self._banned[proxy_url] = time.time() + seconds

    def _format(self, raw: str) -> str:
        if "://" in raw:
            return raw
        return f"{self._protocol}://{raw}"
