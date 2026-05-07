"""URL cleaner — unwraps SERP redirects and strips tracking junk.

Search engines wrap results in click-tracking redirects (e.g. Bing's
``ck/a?u=a1<base64>``, Yahoo's ``r.search.yahoo.com/RU=...``,
DuckDuckGo's ``/l/?uddg=...``, Google's ``/url?q=...``). We unwrap them.

We also strip common tracking params (utm_*, gclid, fbclid, ...) so two URLs
that point at the same logical resource normalise to the same string.
"""

from __future__ import annotations

import base64
import re
import urllib.parse

from .config import TRACKING_PARAMS

_RU_RE = re.compile(r"[?&/]RU=([^&\s]+)")
_RU_TAIL_RE = re.compile(r"/(?:RK|RS|RB|RT|RX|RQ)=.*$")
_BING_U_RE = re.compile(r"u=a1([\w%-]+)")


def _b64_decode_padded(s: str) -> str:
    """Decode a URL-safe base64 string after fixing padding."""
    s = s.replace("-", "+").replace("_", "/")
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s).decode("utf-8", "ignore")


def unwrap_redirect(url: str) -> str:
    """If ``url`` is a known search-engine redirect wrapper, return the
    underlying destination URL. Otherwise return ``url`` unchanged."""
    if not url:
        return url
    low = url.lower()

    # DuckDuckGo
    if "duckduckgo.com/l/" in low and "uddg=" in low:
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if "uddg" in q:
                cand = urllib.parse.unquote(q["uddg"][0])
                if cand.startswith("http"):
                    return cand
        except Exception:
            pass

    # Google /url?q= / /url?url=
    if "google." in low and "/url" in low:
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            for key in ("q", "url"):
                if key in q and q[key] and q[key][0].startswith("http"):
                    return urllib.parse.unquote(q[key][0])
        except Exception:
            pass

    # Yahoo (and AOL) — RU=<encoded>
    if "r.search.yahoo.com" in low or "/ru=" in low or "&ru=" in low:
        m = _RU_RE.search(url)
        if m:
            cand = _RU_TAIL_RE.sub("", m.group(1))
            cand = urllib.parse.unquote(cand)
            if cand.startswith("http"):
                return cand

    # Bing — ck/a?u=a1<base64>
    if "bing.com/ck/a" in low and "u=a1" in low:
        m = _BING_U_RE.search(url)
        if m:
            try:
                cand = urllib.parse.unquote(_b64_decode_padded(m.group(1)))
                if cand.startswith("http"):
                    return cand
            except Exception:
                pass

    # Startpage redirect: /do/redirect?u=<encoded>
    if "startpage.com" in low and ("/do/redirect" in low or "/url" in low):
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            for key in ("u", "url", "q"):
                if key in q and q[key] and q[key][0].startswith("http"):
                    return urllib.parse.unquote(q[key][0])
        except Exception:
            pass

    # Brave search redirect: /search?q=...&source=web (no redirect for results,
    # but the news cluster sometimes uses /goto?u=)
    if "search.brave.com" in low and "u=" in low:
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if "u" in q and q["u"] and q["u"][0].startswith("http"):
                return urllib.parse.unquote(q["u"][0])
        except Exception:
            pass

    # Yandex /clck/jsredir?...&to=<encoded>
    if "yandex." in low and ("/clck/" in low or "/redir/" in low):
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            for key in ("to", "url"):
                if key in q and q[key] and q[key][0].startswith("http"):
                    return urllib.parse.unquote(q[key][0])
        except Exception:
            pass

    return url


def strip_tracking(url: str) -> str:
    """Remove utm_*/gclid/fbclid/etc params from the URL's query string."""
    try:
        pr = urllib.parse.urlparse(url)
    except Exception:
        return url
    if not pr.query:
        return url
    q = urllib.parse.parse_qsl(pr.query, keep_blank_values=True)
    q = [(k, v) for k, v in q if k.lower() not in TRACKING_PARAMS]
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunparse((
        pr.scheme,
        pr.netloc,
        pr.path or "/",
        pr.params,
        new_q,
        "",  # always drop fragment
    ))


def normalise(url: str) -> str:
    """Idempotent normalisation used for dedupe.

    - lowercase scheme + netloc
    - drop ``www.`` prefix
    - collapse double slashes in path
    - sort query params
    """
    try:
        pr = urllib.parse.urlparse(url)
    except Exception:
        return url
    scheme = (pr.scheme or "http").lower()
    netloc = (pr.netloc or "").lower().split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = pr.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    path = path.rstrip("/") or "/"
    if pr.query:
        q = sorted(urllib.parse.parse_qsl(pr.query, keep_blank_values=True))
        query = urllib.parse.urlencode(q)
    else:
        query = ""
    return urllib.parse.urlunparse((scheme, netloc, path, "", query, ""))


def clean(url: str) -> str:
    """One-shot pipeline: unwrap → unquote → strip tracking → trim junk."""
    if not url:
        return url
    s = url.strip()
    if s.startswith("//"):
        s = "https:" + s
    s = urllib.parse.unquote(s)
    s = s.split("#")[0]
    s = unwrap_redirect(s)
    # Strip trailing punctuation that often glues onto URLs in HTML.
    while s and s[-1] in ".,;:)]}>'\"\\":
        s = s[:-1]
    s = strip_tracking(s)
    return s
