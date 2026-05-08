"""Akaza — fast, multi-engine, blocking-resistant dork URL parser."""

from __future__ import annotations

__version__ = "9.0.0"

from .config import Settings
from .dorks import Dork, parse_dork, parse_dorks
from .engines import REGISTRY, BaseEngine, list_engines, make_engine
from .filters import URLFilter, URLStore
from .http import CURL_CFFI_OK
from .proxies import ProxyManager
from .quality import score_url
from .runner import Runner, Stats, default_output_path

__all__ = [
    "CURL_CFFI_OK",
    "REGISTRY",
    "BaseEngine",
    "Dork",
    "ProxyManager",
    "Runner",
    "Settings",
    "Stats",
    "URLFilter",
    "URLStore",
    "__version__",
    "default_output_path",
    "list_engines",
    "make_engine",
    "parse_dork",
    "parse_dorks",
    "score_url",
]
