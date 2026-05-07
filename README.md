# Akaza Dork Parser v9

Fast, multi-engine, blocking-resistant URL extractor for search-engine
dorks.

## What's new in v9

- **14 search engines** — `brave`, `mojeek`, `marginalia`, `startpage`,
  `ecosia`, `qwant`, `searx` (multi-instance), `duckduckgo`, `yandex`,
  `yahoo`, `yahoo_jp`, `aol`, `bing`, `google`. The non-Google/Bing engines
  block far less aggressively, so you can scrape without proxies in many
  cases.
- **TLS fingerprint impersonation** — the HTTP layer prefers
  [`curl_cffi`](https://github.com/lexiforest/curl_cffi) and impersonates
  Chrome 131 (JA3 + HTTP/2 + ALPN). Drops Google/Bing block rate to a tiny
  fraction of v8 even on residential rotating proxies.
- **Per-engine browser-realistic headers** — Sec-CH-UA, Sec-Fetch-*,
  language-aware Accept-Language, Referer chain — built fresh per request,
  not stale 2-year-old cookies.
- **Smart proxy rotation** — bad-proxy ban list with TTL, automatic
  detection of residential gateway hostnames (sticky-session, never
  banned), per-engine cooldown.
- **Quality scoring** — every URL is scored 0..1 and below-threshold URLs
  are dropped. Boosts URLs matching the dork's `.ext?param=` suffix;
  penalises blog tag pages, bare homepages, low-quality hosts.
- **Dork suffix filter** — the legacy `Membresía VIP .htm?cat=` format is
  parsed into `(query="Membresía VIP", ext="htm", param="cat")` and the
  suffix is enforced on every result. v8 dropped the suffix entirely,
  which was the main reason you got "trash" URLs.
- **Concurrent runner** — async fan-out over `dork × engine × page`, with
  a per-engine token-bucket rate limiter so no single engine gets
  hammered.
- **Modular package** — every concern lives in its own module, every
  engine in its own file, fully unit-tested. The legacy
  `python akaza.py` interactive UX is preserved.

## Quick start

```bash
pip install -r requirements.txt

# Interactive TUI (same UX as v8)
python akaza.py

# Or use the CLI directly
python -m akaza scrape -e brave,mojeek,ecosia,qwant,searx -d dorks.txt
python -m akaza engines
python -m akaza proxies validate
```

## CLI

```
python -m akaza scrape \
    -d dorks.txt -o out.txt \
    -e brave,mojeek,marginalia,ecosia,qwant,searx,duckduckgo,yahoo_jp \
    --pages 8 \
    --concurrency 24 \
    --quality 0.40 \
    --proxy-mode file \
    --proxy-protocol http \
    --proxies-file proxies.txt
```

Useful flags:

| Flag | Meaning |
| --- | --- |
| `-e` / `--engines` | Comma-separated engine list. |
| `--pages` | Pages per engine per dork. |
| `--concurrency` | Parallel `(dork, engine)` workers. |
| `--per-engine-concurrency` | Parallel pages within one `(dork, engine)`. |
| `--quality` | Quality threshold (0..1). |
| `--php-only` | Only emit URLs whose path ends in `.php`-family extension. |
| `--require-query` | Only emit URLs that have a `?param=` query string. |
| `--unique-sites` | Emit at most one URL per netloc. |
| `--no-suffix` | Disable the legacy `.ext?param=` filter (treat all dorks as plain queries). |
| `--proxy-mode` | `proxyless`, `file`, or `online`. |
| `--proxy-protocol` | `http`, `socks4`, `socks5`. |
| `--no-curl-cffi` | Disable Chrome JA3 impersonation (use aiohttp only). |
| `--language` | `Accept-Language` header value. |

## Proxies

`proxies.txt` accepts one entry per line in any of:

```
1.2.3.4:8080
http://1.2.3.4:8080
user:pass@gateway.smartproxy.com:7000
http://user:pass@gate.example.net:1080
socks5://1.2.3.4:1080
```

Residential rotating gateways (Smartproxy, BrightData, Oxylabs, IPRoyal,
NetNut, Storm, Webshare, Shifter, etc.) are auto-detected by hostname and
the rotator never bans them — exactly one entry is enough to power the
whole run.

For free public proxies, run `python -m akaza proxies scrape` to populate
`proxies.txt` from public lists, then `python -m akaza proxies validate`
to filter out dead ones.

## Engines

| Engine | Notes |
| --- | --- |
| `brave` | Independent index, low blocking. Best default. |
| `mojeek` | Independent crawler, almost never blocks. Deep niche pages. |
| `marginalia` | Hand-curated index of small / old / long-form web. |
| `startpage` | Google results without Google's anti-bot layer. |
| `ecosia` | Bing-backed but their proxy keeps blocking light. |
| `qwant` | Bing+own EU index. |
| `searx` | Aggregates many engines; rotates across public SearXNG instances. |
| `duckduckgo` | HTML form. POST for pagination. |
| `yandex` | Different index, low blocking outside RU/UA. |
| `yahoo` / `yahoo_jp` / `aol` | Yahoo family. Need `curl_cffi` to be reliable. |
| `bing` / `google` | Heaviest blocking. Use only with good residential proxies and `curl_cffi` enabled. |

`python -m akaza engines` prints the live registry.

## Dork format

Two formats live side-by-side in `dorks.txt`:

```
# Free-text + URL signature suffix
Membresía VIP .htm?cat=
Multiple payment methods .flv?panel=
buy now .php?id=

# Standard search-engine operators (left untouched)
inurl:index.php?id=
site:example.com login
intitle:"admin login"
filetype:pdf budget 2025
```

The `.ext?param=` suffix is parsed into a structural URL filter. Even if
an engine returns 1000 trash URLs for `Membresía VIP`, only the URLs
ending in `.htm` *and* containing `cat=` survive the filter — and those
are then quality-scored.

## Project layout

```
akaza/
  config.py        Settings, blocklists, signal lists, UA pool, Sec-CH-UA
  dorks.py         legacy `text .ext?param=` parser -> Dork(query, suffix)
  cleaner.py       SERP redirect unwrap (Google /url?q, Yahoo RU=, DDG uddg=, Bing ck/a base64)
  filters.py       URLFilter (allow/deny) + URLStore (dedupe, unique-sites)
  quality.py       0..1 scorer
  proxies.py       ProxyManager: file/online/scrape/validate/ban/sticky/rotation
  http.py          curl_cffi-or-aiohttp fetch with smart retry
  rate_limit.py    per-engine token bucket
  engines/         BaseEngine + 14 adapters
  runner.py        async fan-out, writes URLs + stats
  tui.py           interactive menu
  cli.py           argparse CLI
```

## Tests

```bash
python -m pytest tests/ -q
ruff check .
python -m compileall -q akaza akaza.py
```

## License

Same as the original repo.
