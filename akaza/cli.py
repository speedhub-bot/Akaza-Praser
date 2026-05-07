"""Argparse-driven CLI for the Akaza dork parser.

Usage examples:

    python -m akaza scrape --engines brave,mojeek,ecosia
    python -m akaza scrape -d dorks.txt -o out.txt
    python -m akaza engines
    python -m akaza proxies validate
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from . import __version__
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


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="akaza",
        description="Akaza Dork Parser v9 — fast, multi-engine, blocking-resistant",
    )
    p.add_argument("--version", action="version", version=f"akaza {__version__}")
    sub = p.add_subparsers(dest="command")

    sc = sub.add_parser("scrape", help="Run a scrape against the dork list.")
    sc.add_argument("-d", "--dorks", default=DORKS_FILE, help="dorks file")
    sc.add_argument("-o", "--output", default=None, help="output URL list")
    sc.add_argument(
        "-e",
        "--engines",
        default=",".join(DEFAULT_ENGINES),
        help="comma-separated engine names",
    )
    sc.add_argument("--pages", type=int, default=8)
    sc.add_argument("--concurrency", type=int, default=24)
    sc.add_argument("--per-engine-concurrency", type=int, default=3)
    sc.add_argument("--quality", type=float, default=0.40)
    sc.add_argument("--php-only", action="store_true")
    sc.add_argument("--require-query", action="store_true")
    sc.add_argument("--unique-sites", action="store_true")
    sc.add_argument(
        "--no-suffix",
        action="store_true",
        help="ignore the legacy `.ext?param=` dork suffix filter",
    )
    sc.add_argument(
        "--proxy-mode",
        choices=["proxyless", "file", "online"],
        default="proxyless",
    )
    sc.add_argument(
        "--proxy-protocol",
        choices=["http", "socks4", "socks5"],
        default="http",
    )
    sc.add_argument("--proxies-file", default=PROXIES_FILE)
    sc.add_argument(
        "--no-curl-cffi",
        action="store_true",
        help="disable curl_cffi TLS impersonation (use aiohttp only)",
    )
    sc.add_argument(
        "--language",
        default="en-US,en;q=0.9",
        help="Accept-Language header",
    )

    sub.add_parser("engines", help="List available engines.")

    pp = sub.add_parser("proxies", help="Proxy management.")
    pp_sub = pp.add_subparsers(dest="action")
    pp_sub.add_parser("scrape", help="Scrape free proxies from public lists.")
    pp_sub.add_parser("validate", help="Validate proxies in proxies.txt.")
    pp_sub.add_parser("count", help="Print loaded proxy count.")

    return p


def _print_progress(snap: dict) -> None:
    """Render a tight one-line progress bar to stderr."""
    if snap["total"]:
        pct = (snap["done"] / snap["total"]) * 100
    else:
        pct = 0.0
    eng = (snap.get("current_engine") or "-")[:10]
    sys.stderr.write(
        f"\r[{snap['done']:>5}/{snap['total']}] {pct:5.1f}%  "
        f"valid={snap['valid']:<5} dupes={snap['duplicates']:<4} "
        f"rej={snap['rejected']:<5} blk={snap['blocked']:<3} "
        f"err={snap['errors']:<3} eng={eng:<10} "
        f"rate={snap['rate']:.1f}/s   "
    )
    sys.stderr.flush()


async def _cmd_scrape(args) -> int:
    settings = Settings(
        engines=[e.strip().lower() for e in args.engines.split(",") if e.strip()],
        max_pages=args.pages,
        concurrency=args.concurrency,
        per_engine_concurrency=args.per_engine_concurrency,
        quality_threshold=args.quality,
        php_only=args.php_only,
        require_query=args.require_query,
        unique_sites_only=args.unique_sites,
        apply_dork_suffix=not args.no_suffix,
        proxy_mode=args.proxy_mode,
        proxy_protocol=args.proxy_protocol,
        use_curl_cffi=(not args.no_curl_cffi) and CURL_CFFI_OK,
        accept_language=args.language,
    )

    raw_lines = read_lines(args.dorks)
    if not raw_lines:
        print(f"No dorks found in {args.dorks}", file=sys.stderr)
        return 2
    dorks = parse_dorks(raw_lines)
    print(f"Loaded {len(dorks)} dorks from {args.dorks}", file=sys.stderr)

    proxy_mgr = ProxyManager()
    if settings.proxy_mode == "file":
        n = proxy_mgr.load_from_file(args.proxies_file, args.proxy_protocol)
        print(f"Loaded {n} proxies from {args.proxies_file}", file=sys.stderr)
        if n and not proxy_mgr.is_residential and settings.proxy_validate:
            valid = await proxy_mgr.validate(args.proxy_protocol)
            print(f"{valid} proxies validated.", file=sys.stderr)
    elif settings.proxy_mode == "online":
        n = await proxy_mgr.scrape_online(args.proxy_protocol)
        print(f"Scraped {n} proxies online.", file=sys.stderr)
        valid = await proxy_mgr.validate(args.proxy_protocol)
        print(f"{valid} proxies validated.", file=sys.stderr)

    if settings.proxy_mode != "proxyless" and proxy_mgr.count == 0:
        print(
            "No usable proxies — falling back to proxyless.",
            file=sys.stderr,
        )
        settings.proxy_mode = "proxyless"

    output_path = args.output or default_output_path(settings)
    runner = Runner(settings, proxy_manager=proxy_mgr, progress_cb=_print_progress)
    valid = await runner.run(dorks, output_path)

    sys.stderr.write("\n")
    sys.stderr.flush()
    snap = runner.stats.snapshot()
    print(f"\nDone. Valid URLs: {valid}")
    print(f"Output: {output_path}")
    print(f"Found: {snap['found']}  Duplicates: {snap['duplicates']}  "
          f"Rejected: {snap['rejected']}  Blocked: {snap['blocked']}  "
          f"Soft-blocked: {snap['soft_blocked']}  Errors: {snap['errors']}")
    if snap["per_engine"]:
        print("Per-engine valid URLs:")
        for k, v in sorted(snap["per_engine"].items(), key=lambda kv: -kv[1]):
            print(f"  {k:<14} {v}")
    return 0 if valid > 0 else 1


def _cmd_engines() -> int:
    print("Available engines:")
    for e in list_engines():
        print(f"  {e}")
    print(f"\ncurl_cffi available: {CURL_CFFI_OK}")
    return 0


async def _cmd_proxies(args) -> int:
    pm = ProxyManager()
    if args.action == "scrape":
        n = await pm.scrape_online("http")
        print(f"Scraped {n} proxies, validating…")
        v = await pm.validate("http")
        print(f"{v} validated proxies. Writing to {PROXIES_FILE}")
        with open(PROXIES_FILE, "w", encoding="utf-8") as f:
            for raw in pm._proxies:
                f.write(raw + "\n")
        return 0
    if args.action == "validate":
        if not os.path.exists(PROXIES_FILE):
            print(f"{PROXIES_FILE} not found.")
            return 2
        n = pm.load_from_file(PROXIES_FILE, "http")
        print(f"Loaded {n} proxies, validating…")
        v = await pm.validate("http")
        print(f"{v}/{n} valid")
        return 0
    if args.action == "count":
        n = pm.load_from_file(PROXIES_FILE, "http")
        print(f"{n} proxies in {PROXIES_FILE}")
        return 0
    print("Unknown proxies action. Use: scrape | validate | count")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "scrape":
        return asyncio.run(_cmd_scrape(args))
    if args.command == "engines":
        return _cmd_engines()
    if args.command == "proxies":
        return asyncio.run(_cmd_proxies(args))
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
