"""Dork parser.

Handles two dork formats in the same file:

1. **Legacy "URL signature" dorks** (``Membresía VIP .htm?cat=``): a free-text
   query suffixed with the path-extension and query-param hint that the user
   wants the resulting URL to *contain*. The old code dropped the suffix —
   we keep it as a structured filter.

2. **Standard search operators** (``inurl:index.php?id=`` / ``site:example.com``
   / ``intitle:foo``): used as-is.

The :class:`Dork` it returns is what every engine adapter sees, and what the
quality scorer uses to give a score boost when a URL matches.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field

# Recognized search-engine operators (case-insensitive).
_OPERATOR_RE = re.compile(
    r"\b(?:inurl|allinurl|intitle|allintitle|intext|allintext|"
    r"site|filetype|cache|inanchor|allinanchor|ext)[: ]",
    re.IGNORECASE,
)

# Trailing dork suffix: ``.ext`` optionally followed by ``?param=`` or ``?param``.
# Matches things like:
#   "  .htm?cat="
#   " .php?id="
#   " .aspx?login_id="
#   " .htm"  (no param)
_SUFFIX_RE = re.compile(
    r"""\s+
        (?P<dot>\.)
        (?P<ext>[A-Za-z0-9]{1,8})
        (?:
            \?
            (?P<param>[A-Za-z_][A-Za-z0-9_-]*)
            =?
        )?
        \s*$
    """,
    re.VERBOSE,
)


@dataclass
class Dork:
    """A parsed dork.

    Attributes:
        raw: the original line.
        query: the search-engine query string (with operators preserved
            if present, otherwise just the cleaned text).
        ext: a path extension hint (without the dot) or ``""``.
        param: a query-string parameter name hint or ``""``.
        operators: True iff the dork uses ``inurl:`` / ``site:`` / etc.
            When True, the engine will pass ``query`` straight through and
            we skip the suffix filter (those operators already filter).
    """

    raw: str
    query: str
    ext: str = ""
    param: str = ""
    operators: bool = False
    extras: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def matches(self, url: str) -> bool:
        """Return True iff ``url`` satisfies this dork's structural filter.

        - When the dork uses operators (``inurl:`` / ``filetype:`` / ...),
          we trust the engine to filter and just return True.
        - Otherwise we require that the URL's path ends in ``.ext`` (if set)
          AND that ``param`` (if set) appears in the query string.
        """
        if self.operators:
            return True
        if not self.ext and not self.param:
            return True
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return False
        path = (parsed.path or "").lower()
        if self.ext:
            if not path.endswith("." + self.ext.lower()):
                # Be lenient on .htm/.html — they're often interchangeable
                if self.ext.lower() in {"htm", "html"} and (
                    path.endswith(".htm") or path.endswith(".html")
                ):
                    pass
                else:
                    return False
        if self.param:
            qs = parsed.query or ""
            if not qs:
                return False
            keys = {
                k.lower()
                for k, _ in urllib.parse.parse_qsl(qs, keep_blank_values=True)
            }
            if self.param.lower() not in keys:
                return False
        return True


def parse_dork(raw: str) -> Dork:
    """Parse a single line of ``dorks.txt`` into a :class:`Dork`."""
    if raw is None:
        return Dork(raw="", query="")
    line = raw.strip()
    if not line:
        return Dork(raw=raw, query="")

    # Operators short-circuit suffix parsing
    if _OPERATOR_RE.search(line):
        return Dork(raw=raw, query=line, operators=True)

    m = _SUFFIX_RE.search(line)
    if m:
        ext = m.group("ext").lower()
        param = (m.group("param") or "").strip()
        cleaned = line[: m.start()].strip()
        return Dork(
            raw=raw,
            query=cleaned or line,
            ext=ext,
            param=param,
        )

    return Dork(raw=raw, query=line)


def parse_dorks(lines: list[str]) -> list[Dork]:
    """Parse a list of raw lines, dropping ones that come out empty."""
    out: list[Dork] = []
    for line in lines:
        d = parse_dork(line)
        if d.query:
            out.append(d)
    return out
