"""Interactive TUI — keeps the original ``python akaza.py`` UX.

Loops over a small set of menus (Main / Settings / Proxies) backed by the
new :class:`akaza.runner.Runner`.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

try:
    from colorama import Fore, Style
    from colorama import init as colorama_init
    colorama_init(autoreset=True)
except ImportError:  # pragma: no cover - color is optional
    class _Stub:
        def __getattr__(self, _name: str) -> str:
            return ""
    Fore = _Stub()
    Style = _Stub()

from .config import (
    DEFAULT_ENGINES,
    DORKS_FILE,
    PROXIES_FILE,
    Settings,
    read_lines,
)
from .dorks import parse_dorks
from .engines import list_engines
from .http import CURL_CFFI_OK
from .proxies import ProxyManager
from .runner import Runner, default_output_path


def _clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


class App:
    """Interactive menu wrapper."""

    def __init__(self) -> None:
        self.settings = Settings()
        self.proxy_mgr = ProxyManager()

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def header(self) -> None:
        _clear()
        curl_status = (Fore.GREEN + "ON") if CURL_CFFI_OK else (Fore.RED + "OFF")
        print(Fore.CYAN + Style.BRIGHT + "AKAZA DORK PARSER v9.0" + Style.RESET_ALL)
        print(
            Fore.LIGHTBLACK_EX
            + f"  curl_cffi (Chrome 131 JA3): {curl_status}"
            + Style.RESET_ALL
        )
        print(
            Fore.LIGHTBLACK_EX
            + f"  Proxies loaded: {self.proxy_mgr.count}  "
            f"({'residential' if self.proxy_mgr.is_residential else 'rotating'})"
            + Style.RESET_ALL
        )
        print(Fore.LIGHTBLACK_EX + "-" * 70 + Style.RESET_ALL)

    def _ask(self, prompt: str, default: str = "") -> str:
        try:
            s = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return default
        return s or default

    def menu(self, title: str, options: dict[str, str]) -> str:
        while True:
            self.header()
            print(Fore.YELLOW + title + Style.RESET_ALL)
            for k, v in options.items():
                print(f"  [{k}] {v}")
            choice = self._ask("> ").strip()
            if choice in options:
                return choice

    # ------------------------------------------------------------------
    # Proxy menu
    # ------------------------------------------------------------------

    async def proxy_flow(self) -> None:
        while True:
            choice = self.menu(
                f"Proxy Management  ({self.proxy_mgr.protocol}, count={self.proxy_mgr.count})",
                {
                    "1": "Load from proxies.txt",
                    "2": "Scrape free proxies online",
                    "3": "Validate loaded proxies",
                    "4": "Clear pool",
                    "0": "Back",
                },
            )
            if choice == "1":
                proto = self._ask(
                    "Protocol (http/socks4/socks5) [http]: ", "http"
                ).lower()
                if proto not in {"http", "socks4", "socks5"}:
                    proto = "http"
                n = self.proxy_mgr.load_from_file(PROXIES_FILE, proto)
                tag = (
                    "residential gateway"
                    if self.proxy_mgr.is_residential
                    else "rotating list"
                )
                print(f"Loaded {n} proxies ({tag})")
                self._ask("Press Enter… ")
            elif choice == "2":
                proto = self._ask(
                    "Protocol (http/socks4/socks5) [http]: ", "http"
                ).lower()
                if proto not in {"http", "socks4", "socks5"}:
                    proto = "http"
                print("Scraping…")
                n = await self.proxy_mgr.scrape_online(proto)
                print(f"Scraped {n} proxies")
                self._ask("Press Enter… ")
            elif choice == "3":
                if self.proxy_mgr.is_residential:
                    print(
                        "Skipping validation — residential gateway detected."
                    )
                    self._ask("Press Enter… ")
                    continue
                print("Validating (this may take a while)…")
                n = await self.proxy_mgr.validate(self.proxy_mgr.protocol)
                print(f"{n} valid proxies remain")
                self._ask("Press Enter… ")
            elif choice == "4":
                self.proxy_mgr.clear()
                print("Cleared.")
                self._ask("Press Enter… ")
            else:
                return

    # ------------------------------------------------------------------
    # Settings menu
    # ------------------------------------------------------------------

    def settings_flow(self) -> None:
        while True:
            choice = self.menu(
                "Settings",
                {
                    "1": f"Concurrency: {self.settings.concurrency}",
                    "2": f"Per-engine pages: {self.settings.max_pages}",
                    "3": f"Per-engine concurrency: {self.settings.per_engine_concurrency}",
                    "4": f"Engines: {', '.join(self.settings.engines)}",
                    "5": f"Quality threshold: {self.settings.quality_threshold:.2f}",
                    "6": f"PHP-only: {'ON' if self.settings.php_only else 'OFF'}",
                    "7": f"Require ?param=: {'ON' if self.settings.require_query else 'OFF'}",
                    "8": f"Unique sites: {'ON' if self.settings.unique_sites_only else 'OFF'}",
                    "9": f"Apply dork suffix filter: {'ON' if self.settings.apply_dork_suffix else 'OFF'}",
                    "a": f"Proxy mode: {self.settings.proxy_mode} ({self.settings.proxy_protocol})",
                    "b": f"curl_cffi (Chrome JA3): {'ON' if self.settings.use_curl_cffi else 'OFF'}",
                    "c": f"Fast mode: {'ON' if self.settings.fast_mode else 'OFF'}",
                    "0": "Back",
                },
            )
            if choice == "1":
                v = self._ask("New concurrency (1-200): ")
                if v.isdigit():
                    self.settings.concurrency = max(1, min(200, int(v)))
            elif choice == "2":
                v = self._ask("Pages per engine (1-50): ")
                if v.isdigit():
                    self.settings.max_pages = max(1, min(50, int(v)))
            elif choice == "3":
                v = self._ask("Per-engine concurrency (1-10): ")
                if v.isdigit():
                    self.settings.per_engine_concurrency = max(1, min(10, int(v)))
            elif choice == "4":
                print("Available:", ", ".join(list_engines()))
                v = self._ask(
                    "Engines (comma-separated, blank=default): ",
                    ",".join(DEFAULT_ENGINES),
                )
                chosen = [
                    e.strip().lower() for e in v.split(",") if e.strip()
                ]
                if chosen:
                    self.settings.engines = chosen
            elif choice == "5":
                v = self._ask("Quality threshold 0..1: ")
                try:
                    self.settings.quality_threshold = max(
                        0.0, min(1.0, float(v))
                    )
                except ValueError:
                    pass
            elif choice == "6":
                self.settings.php_only = not self.settings.php_only
            elif choice == "7":
                self.settings.require_query = not self.settings.require_query
            elif choice == "8":
                self.settings.unique_sites_only = (
                    not self.settings.unique_sites_only
                )
            elif choice == "9":
                self.settings.apply_dork_suffix = (
                    not self.settings.apply_dork_suffix
                )
            elif choice == "a":
                m = self._ask(
                    "Mode (proxyless/file/online): ", self.settings.proxy_mode
                ).lower()
                if m in {"proxyless", "file", "online"}:
                    self.settings.proxy_mode = m
                if self.settings.proxy_mode != "proxyless":
                    p = self._ask(
                        "Protocol (http/socks4/socks5): ",
                        self.settings.proxy_protocol,
                    ).lower()
                    if p in {"http", "socks4", "socks5"}:
                        self.settings.proxy_protocol = p
            elif choice == "b":
                if not CURL_CFFI_OK:
                    print(
                        "curl_cffi is not installed. "
                        "Run: pip install curl_cffi"
                    )
                    self._ask("Press Enter… ")
                    continue
                self.settings.use_curl_cffi = not self.settings.use_curl_cffi
            elif choice == "c":
                self.settings.fast_mode = not self.settings.fast_mode
            else:
                return

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run_parser(self) -> None:
        self.header()
        raw = read_lines(DORKS_FILE)
        if not raw:
            print(Fore.RED + f"No dorks in {DORKS_FILE}")
            self._ask("Press Enter… ")
            return
        dorks = parse_dorks(raw)
        print(f"Loaded {len(dorks)} dorks")

        if self.settings.proxy_mode == "file" and self.proxy_mgr.count == 0:
            self.proxy_mgr.load_from_file(
                PROXIES_FILE, self.settings.proxy_protocol
            )
            if (
                self.proxy_mgr.count
                and not self.proxy_mgr.is_residential
            ):
                print("Validating proxies…")
                await self.proxy_mgr.validate(self.settings.proxy_protocol)
        if self.settings.proxy_mode == "online" and self.proxy_mgr.count == 0:
            await self.proxy_mgr.scrape_online(self.settings.proxy_protocol)
            await self.proxy_mgr.validate(self.settings.proxy_protocol)
        if (
            self.settings.proxy_mode != "proxyless"
            and self.proxy_mgr.count == 0
        ):
            print(Fore.YELLOW + "No proxies loaded — falling back to proxyless.")
            self.settings.proxy_mode = "proxyless"
            await asyncio.sleep(1)

        out_path = default_output_path(self.settings)
        last = {"v": 0}

        def _cb(snap: dict) -> None:
            last["v"] = snap["valid"]
            sys.stdout.write(
                f"\r[{snap['done']:>5}/{snap['total']}]  "
                f"valid={snap['valid']:<5} dupes={snap['duplicates']:<4} "
                f"rej={snap['rejected']:<4} blk={snap['blocked']:<3} "
                f"err={snap['errors']:<3} eng={(snap.get('current_engine') or '-')[:10]:<10} "
                f"rate={snap['rate']:.1f}/s   "
            )
            sys.stdout.flush()

        runner = Runner(
            self.settings,
            proxy_manager=self.proxy_mgr,
            progress_cb=_cb,
        )
        t0 = time.time()
        await runner.run(dorks, out_path)
        elapsed = time.time() - t0

        sys.stdout.write("\n")
        snap = runner.stats.snapshot()
        print(
            Fore.GREEN
            + f"\nDone in {elapsed:.1f}s  Valid URLs: {snap['valid']}  "
            f"file: {os.path.basename(out_path)}"
        )
        print(Fore.LIGHTBLACK_EX + f"  Path: {out_path}")
        if snap["per_engine"]:
            print(Fore.LIGHTBLACK_EX + "  Per-engine:")
            for k, v in sorted(snap["per_engine"].items(), key=lambda kv: -kv[1]):
                print(Fore.LIGHTBLACK_EX + f"    {k:<14} {v}")
        self._ask("\nPress Enter to continue… ")

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def main(self) -> None:
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
