"""HTTP fetch layer.

Uses ``curl_cffi`` (Chrome 131 JA3 impersonation) when available, with
aiohttp as a fallback. Builds realistic per-engine headers.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import aiohttp

from .config import SEC_CH_UA_BY_CHROME, USER_AGENTS, Settings

if TYPE_CHECKING:
    pass

# Try to load curl_cffi for TLS impersonation.
try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    CURL_CFFI_OK = True
except ImportError:
    CurlAsyncSession = None  # type: ignore[assignment,misc]
    CURL_CFFI_OK = False


# ---------------------------------------------------------------------------
# Per-engine header templates
# ---------------------------------------------------------------------------

def _chrome_headers(
    ua: str,
    referer: str,
    *,
    accept_lang: str = "en-US,en;q=0.9",
    ch_ua: str | None = None,
) -> dict[str, str]:
    """Build a Chrome-shaped header set."""
    return {
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": accept_lang,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": referer,
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        **(
            {
                "Sec-Ch-Ua": ch_ua,
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Linux"',
            }
            if ch_ua
            else {}
        ),
    }


_ENGINE_REFERERS: dict[str, str] = {
    "google": "https://www.google.com/",
    "bing": "https://www.bing.com/",
    "brave": "https://search.brave.com/",
    "mojeek": "https://www.mojeek.com/",
    "startpage": "https://www.startpage.com/",
    "yandex": "https://yandex.com/",
    "ecosia": "https://www.ecosia.org/",
    "qwant": "https://www.qwant.com/",
    "duckduckgo": "https://duckduckgo.com/",
    "yahoo": "https://search.yahoo.com/",
    "yahoo_jp": "https://www.yahoo.co.jp/",
    "aol": "https://www.aol.com/",
    "searx": "https://searx.be/",
    "marginalia": "https://search.marginalia.nu/",
}


def headers_for_engine(
    engine: str,
    settings: Settings,
) -> dict[str, str]:
    """Return a browser-realistic header dict for *engine*."""
    ua = random.choice(USER_AGENTS)
    referer = _ENGINE_REFERERS.get(engine, "https://www.google.com/")
    ch_ua = SEC_CH_UA_BY_CHROME.get("131")
    return _chrome_headers(ua, referer, accept_lang=settings.accept_language, ch_ua=ch_ua)


# ---------------------------------------------------------------------------
# Unified fetch helpers
# ---------------------------------------------------------------------------


async def fetch_curl(
    url: str,
    *,
    headers: dict[str, str],
    proxy: str | None = None,
    timeout: float = 22.0,
    method: str = "GET",
    data: dict | None = None,
) -> str | None:
    """Fetch using ``curl_cffi`` with Chrome 131 impersonation."""
    if not CURL_CFFI_OK:
        return None
    try:
        async with CurlAsyncSession(impersonate="chrome131") as sess:
            if method.upper() == "POST":
                r = await sess.post(
                    url, headers=headers, proxy=proxy, data=data,
                    timeout=timeout, allow_redirects=True, verify=False,
                )
            else:
                r = await sess.get(
                    url, headers=headers, proxy=proxy,
                    timeout=timeout, allow_redirects=True, verify=False,
                )
            if r.status_code == 200:
                return r.text
            return None
    except Exception:
        return None


async def fetch_aiohttp(
    url: str,
    *,
    headers: dict[str, str],
    proxy: str | None = None,
    timeout: float = 22.0,
    method: str = "GET",
    data: dict | None = None,
) -> str | None:
    """Fetch using plain ``aiohttp`` (no TLS impersonation)."""
    to = aiohttp.ClientTimeout(total=timeout)
    connector = None
    if proxy and proxy.startswith("socks"):
        try:
            from aiohttp_socks import ProxyConnector
            connector = ProxyConnector.from_url(proxy)
        except ImportError:
            return None

    try:
        async with aiohttp.ClientSession(
            connector=connector, timeout=to, headers=headers
        ) as sess:
            kw: dict = {"ssl": False}
            if proxy and not proxy.startswith("socks"):
                kw["proxy"] = proxy
            if method.upper() == "POST":
                async with sess.post(url, data=data, **kw) as r:
                    if r.status == 200:
                        return await r.text()
                    return None
            else:
                async with sess.get(url, **kw) as r:
                    if r.status == 200:
                        return await r.text()
                    return None
    except Exception:
        return None


async def fetch(
    url: str,
    *,
    engine: str,
    settings: Settings,
    proxy: str | None = None,
    method: str = "GET",
    data: dict | None = None,
    prefer_curl: bool | None = None,
) -> str | None:
    """Unified fetch: tries ``curl_cffi`` first (for TLS-sensitive engines),
    then falls back to ``aiohttp``.

    Returns the response body text or ``None`` on failure.
    """
    hdrs = headers_for_engine(engine, settings)
    use_curl = (
        (prefer_curl if prefer_curl is not None else settings.use_curl_cffi)
        and CURL_CFFI_OK
    )
    timeout = settings.request_timeout

    if use_curl:
        text = await fetch_curl(
            url, headers=hdrs, proxy=proxy, timeout=timeout,
            method=method, data=data,
        )
        if text is not None:
            return text

    # Fallback to aiohttp
    return await fetch_aiohttp(
        url, headers=hdrs, proxy=proxy, timeout=timeout,
        method=method, data=data,
    )
