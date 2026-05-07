"""Engine registry + factory."""

from __future__ import annotations

from .aol import AOLEngine
from .base import BaseEngine
from .bing import BingEngine
from .brave import BraveEngine
from .duckduckgo import DuckDuckGoEngine
from .ecosia import EcosiaEngine
from .google import GoogleEngine
from .marginalia import MarginaliaEngine
from .mojeek import MojeekEngine
from .qwant import QwantEngine
from .searx import SearxEngine
from .startpage import StartpageEngine
from .yahoo import YahooEngine
from .yahoo_jp import YahooJPEngine
from .yandex import YandexEngine

REGISTRY: dict[str, type[BaseEngine]] = {
    "google": GoogleEngine,
    "bing": BingEngine,
    "brave": BraveEngine,
    "mojeek": MojeekEngine,
    "startpage": StartpageEngine,
    "yandex": YandexEngine,
    "ecosia": EcosiaEngine,
    "qwant": QwantEngine,
    "duckduckgo": DuckDuckGoEngine,
    "yahoo": YahooEngine,
    "yahoo_jp": YahooJPEngine,
    "aol": AOLEngine,
    "searx": SearxEngine,
    "marginalia": MarginaliaEngine,
}

# Friendly aliases.
_ALIASES = {
    "duck": "duckduckgo",
    "ddg": "duckduckgo",
    "yahoo-jp": "yahoo_jp",
    "yahoojp": "yahoo_jp",
    "yj": "yahoo_jp",
    "searxng": "searx",
}


def make_engine(name: str) -> BaseEngine:
    """Instantiate an engine by name (case-insensitive)."""
    key = (name or "").strip().lower()
    key = _ALIASES.get(key, key)
    cls = REGISTRY.get(key)
    if not cls:
        raise KeyError(f"Unknown engine: {name!r}")
    return cls()


def list_engines() -> list[str]:
    return list(REGISTRY.keys())


__all__ = [
    "BaseEngine",
    "REGISTRY",
    "make_engine",
    "list_engines",
    *(cls.__name__ for cls in REGISTRY.values()),
]
