"""Quality scorer for extracted URLs.

Returns a float in ``[0.0, 1.0]``. The runner rejects anything below the
``Settings.quality_threshold`` (default 0.4).

Signals taken into account:
- The dork's own ``ext`` and ``param`` filter (huge boost on match).
- ``inurl:`` / ``intext:`` / ``site:`` matches when the dork uses operators.
- Path extension belongs to ``SIGNAL_EXTENSIONS`` (.php, .asp, ...).
- URL has ``?param=value`` query string.
- URL path contains a recognised "signal keyword" (``index.php``, ``view.php``).
- Penalties for known low-quality hosts, all-numeric paths, ``/feed/``,
  category-listing slugs, and over-long path depth.
"""

from __future__ import annotations

import os
import re
import urllib.parse

from .config import (
    LOW_QUALITY_HOSTS,
    SIGNAL_EXTENSIONS,
    SIGNAL_PATH_KEYWORDS,
)
from .dorks import Dork

_SLUG_LOW_VALUE = re.compile(
    r"/(category|tag|tags|topics?|page|archive|archives|feed|sitemap"
    r"|robots\.txt|terms|privacy|about|contact|help)/?",
    re.IGNORECASE,
)
_DATE_PATH = re.compile(r"/\d{4}/\d{1,2}(?:/\d{1,2})?/")


def score_url(url: str, dork: Dork | None = None) -> float:
    """Return a quality score in ``[0, 1]`` for ``url`` under ``dork``."""
    if not url or not url.startswith("http"):
        return 0.0
    try:
        pr = urllib.parse.urlparse(url)
    except Exception:
        return 0.0
    host = (pr.netloc or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    path = (pr.path or "/").lower()
    query = pr.query or ""
    ext = os.path.splitext(path.split("?")[0])[1].lower()

    score = 0.5  # neutral baseline

    # ---- Positive signals ------------------------------------------------
    if ext in SIGNAL_EXTENSIONS:
        score += 0.20
    elif ext in {".html", ".htm"}:
        score += 0.05
    elif ext == "":
        # No extension is fine for clean URLs but doesn't earn a boost.
        pass

    if query:
        score += 0.15
        # Multiple params is even better
        if query.count("=") >= 2:
            score += 0.05

    for kw in SIGNAL_PATH_KEYWORDS:
        if kw in path:
            score += 0.10
            break

    # Dork-suffix matches: huge boost — this URL exactly matches what the user
    # is looking for.
    if dork is not None and not dork.operators:
        if dork.ext and path.endswith("." + dork.ext.lower()):
            score += 0.30
        if dork.param:
            keys = {
                k.lower()
                for k, _ in urllib.parse.parse_qsl(query, keep_blank_values=True)
            }
            if dork.param.lower() in keys:
                score += 0.30

    # Operator dorks: reward URLs that *contain* the inurl token.
    if dork is not None and dork.operators:
        for m in re.finditer(
            r"inurl:\"?([^\"\s]+)\"?", dork.query, re.IGNORECASE
        ):
            tok = m.group(1).strip().lower()
            if tok and tok in url.lower():
                score += 0.20
                break

    # ---- Negative signals ------------------------------------------------
    if host in LOW_QUALITY_HOSTS:
        score -= 0.25
    if _SLUG_LOW_VALUE.search(path):
        score -= 0.20
    if _DATE_PATH.search(path):
        score -= 0.05  # blog post pattern; only slight penalty

    # Excessive path depth (>= 8 segments) is usually generated junk.
    depth = len([p for p in path.split("/") if p])
    if depth >= 8:
        score -= 0.10
    elif depth == 0:
        score -= 0.10  # bare homepages are rarely interesting dork hits

    # Pure numeric paths (e.g. /12345) are usually IDs without context.
    parts = [p for p in path.split("/") if p]
    if parts and all(p.isdigit() for p in parts):
        score -= 0.10

    return max(0.0, min(1.0, score))
