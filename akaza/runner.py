"""Concurrent runner that fans out (dork x engine x page) and writes URLs."""

from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock

from . import cleaner, http
from .config import Settings
from .dorks import Dork
from .engines import REGISTRY, BaseEngine, make_engine
from .filters import URLFilter, URLStore
from .proxies import ProxyManager
from .quality import score_url
from .rate_limit import EngineRateLimiter

_PROGRESS_LOCK = Lock()


@dataclass
class Stats:
    total_dorks: int = 0
    dorks_done: int = 0
    found: int = 0
    valid: int = 0
    duplicates: int = 0
    rejected: int = 0
    blocked: int = 0
    soft_blocked: int = 0
    errors: int = 0
    retries: int = 0
    started_at: float = field(default_factory=time.time)
    current_dork: str = ""
    current_engine: str = ""
    per_engine_valid: dict[str, int] = field(default_factory=dict)

    def snapshot(self) -> dict:
        elapsed = max(1.0, time.time() - self.started_at)
        return {
            "total": self.total_dorks,
            "done": self.dorks_done,
            "found": self.found,
            "valid": self.valid,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "blocked": self.blocked,
            "soft_blocked": self.soft_blocked,
            "errors": self.errors,
            "retries": self.retries,
            "elapsed": elapsed,
            "rate": self.valid / elapsed,
            "current_dork": self.current_dork,
            "current_engine": self.current_engine,
            "per_engine": dict(self.per_engine_valid),
        }


class Runner:
    """Orchestrates the whole scrape: dork x engine x page fan-out."""

    def __init__(
        self,
        settings: Settings,
        *,
        proxy_manager: ProxyManager | None = None,
        progress_cb=None,
    ) -> None:
        self.settings = settings
        self.proxy_manager = proxy_manager or ProxyManager()
        self.url_filter = URLFilter(
            php_only=settings.php_only,
            require_query=settings.require_query,
        )
        self.store = URLStore(unique_site_only=settings.unique_sites_only)
        self.stats = Stats()
        self.rate = EngineRateLimiter(default_rate=0.6 if settings.fast_mode else 0.4)
        self._engines: dict[str, BaseEngine] = {}
        self._file_lock = asyncio.Lock()
        self._progress_cb = progress_cb

    # ------------------------------------------------------------------
    # Engine cache
    # ------------------------------------------------------------------

    def _engine(self, name: str) -> BaseEngine:
        e = self._engines.get(name)
        if e is None:
            e = make_engine(name)
            self._engines[name] = e
        return e

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    async def run(self, dorks: list[Dork], output_path: str) -> int:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

        engines = [
            n for n in self.settings.normalised_engines() if n in REGISTRY
        ]
        if not engines:
            raise ValueError("No valid engines selected.")

        self.stats.total_dorks = len(dorks) * len(engines)
        self.stats.started_at = time.time()

        sem = asyncio.Semaphore(self.settings.concurrency)

        async def _worker(dork: Dork, engine_name: str) -> None:
            async with sem:
                with _PROGRESS_LOCK:
                    self.stats.current_dork = dork.query
                    self.stats.current_engine = engine_name
                try:
                    await self._scrape_one(dork, engine_name, output_path)
                except Exception:
                    self.stats.errors += 1
                finally:
                    with _PROGRESS_LOCK:
                        self.stats.dorks_done += 1
                    if self._progress_cb is not None:
                        try:
                            self._progress_cb(self.stats.snapshot())
                        except Exception:
                            pass

        tasks = [
            asyncio.create_task(_worker(d, e)) for d in dorks for e in engines
        ]
        if not tasks:
            return 0
        await asyncio.gather(*tasks)
        return self.stats.valid

    # ------------------------------------------------------------------
    # Per (dork, engine) scrape
    # ------------------------------------------------------------------

    async def _scrape_one(
        self, dork: Dork, engine_name: str, output_path: str
    ) -> None:
        engine = self._engine(engine_name)

        # Page-level concurrency inside this single (dork, engine).
        page_sem = asyncio.Semaphore(self.settings.per_engine_concurrency)

        async def _fetch_page(page: int) -> str | None:
            async with page_sem:
                await self.rate.acquire(engine_name)
                # Small jitter so concurrent pages don't all hit at once.
                await asyncio.sleep(random.uniform(0.1, 0.4) * page)
                return await self._fetch(engine, dork, page)

        results = await asyncio.gather(
            *[_fetch_page(p) for p in range(self.settings.max_pages)]
        )

        for page_idx, html in enumerate(results):
            if not html:
                # If page 0 is blocked / empty, give up on later pages.
                if page_idx == 0:
                    return
                continue
            await self._process(html, engine, dork, output_path)

    # ------------------------------------------------------------------
    # HTTP fetch with retries + proxy rotation
    # ------------------------------------------------------------------

    async def _fetch(
        self,
        engine: BaseEngine,
        dork: Dork,
        page: int,
    ) -> str | None:
        url = engine.build_url(dork.query, page)
        method = engine.method
        post_data = engine.post_data(dork.query, page) if method == "POST" else None

        last_proxy: str | None = None
        for attempt in range(self.settings.max_retries):
            proxy = (
                self.proxy_manager.next_proxy()
                if self.settings.proxy_mode != "proxyless"
                else None
            )
            last_proxy = proxy
            try:
                html = await http.fetch(
                    url,
                    engine=engine.name,
                    settings=self.settings,
                    proxy=proxy,
                    method=method,
                    data=post_data,
                    prefer_curl=engine.prefer_curl or self.settings.use_curl_cffi,
                )
            except Exception:
                self.stats.errors += 1
                html = None

            if not html:
                self.stats.retries += 1
                if proxy:
                    self.proxy_manager.ban(proxy, seconds=120)
                self.rate.set_cooldown(engine.name, 4 * (attempt + 1))
                await asyncio.sleep(random.uniform(0.6, 1.4) * (attempt + 1))
                continue

            if engine.is_blocked(html):
                self.stats.blocked += 1
                if proxy:
                    self.proxy_manager.ban(proxy, seconds=300)
                self.rate.set_cooldown(engine.name, 8 * (attempt + 1))
                await asyncio.sleep(random.uniform(1.0, 2.5) * (attempt + 1))
                continue

            if engine.is_empty(html):
                self.stats.soft_blocked += 1
                # Soft-empty is not necessarily a fault of the engine, but
                # can be a soft block — small backoff and retry once.
                await asyncio.sleep(random.uniform(0.5, 1.5))
                if attempt == 0:
                    continue
                return html

            return html

        # All retries failed; record last proxy if any
        if last_proxy:
            self.proxy_manager.ban(last_proxy, seconds=300)
        return None

    # ------------------------------------------------------------------
    # Process extracted HTML
    # ------------------------------------------------------------------

    async def _process(
        self,
        html: str,
        engine: BaseEngine,
        dork: Dork,
        output_path: str,
    ) -> None:
        raw_links = engine.extract(html)
        if not raw_links:
            return
        with _PROGRESS_LOCK:
            self.stats.found += len(raw_links)
            self.stats.per_engine_valid.setdefault(engine.name, 0)

        for raw in raw_links:
            cleaned = cleaner.clean(raw)
            if not cleaned or not cleaned.startswith("http"):
                continue
            if not self.url_filter.is_valid(cleaned):
                self.stats.rejected += 1
                continue
            if self.settings.apply_dork_suffix and not dork.matches(cleaned):
                self.stats.rejected += 1
                continue
            score = score_url(cleaned, dork)
            if score < self.settings.quality_threshold:
                self.stats.rejected += 1
                continue
            if not self.store.add(cleaned):
                self.stats.duplicates += 1
                continue
            with _PROGRESS_LOCK:
                self.stats.valid += 1
                self.stats.per_engine_valid[engine.name] = (
                    self.stats.per_engine_valid.get(engine.name, 0) + 1
                )
            await self._write(output_path, cleaned)

    async def _write(self, path: str, url: str) -> None:
        async with self._file_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(url + "\n")


def default_output_path(settings: Settings) -> str:
    os.makedirs(settings.output_dir, exist_ok=True)
    return os.path.join(
        settings.output_dir,
        f"urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
    )
