---
name: testing-akaza
description: End-to-end test workflow for the Akaza dork parser. Use when verifying engine extractors, dork suffix filtering, quality scoring, proxy rotation, or CLI surface changes.
---

# Testing the Akaza dork parser end-to-end

Repo: `speedhub-bot/Akaza-Praser`. Modular `akaza/` package with 14 search engines, curl_cffi TLS impersonation, async runner.

## TL;DR test commands

```bash
ruff check .
python -m compileall -q akaza akaza.py
python -m pytest tests/ -q                    # 128+ tests, all offline
python -m akaza engines                       # smoke: 14 engines listed
python akaza.py engines                       # legacy shim parity
```

## Engine tiers on datacenter IPs (no proxies)

This is the single biggest gotcha when testing live extraction from a Devin VM.

| Tier | Engines | Behaviour from datacenter IP |
|---|---|---|
| **B** (extractable) | `qwant`, `startpage`, `marginalia`, `yandex`, `yahoo`, `yahoo_jp`, `aol`, `google`, `bing` | Returns 200 OK HTML — BUT `yandex`/`yahoo`/`aol`/`google` then return captcha or interstitial pages. Only `qwant`/`startpage`/`marginalia`/`yahoo_jp`/`bing` actually produce extractable URLs. |
| **C** (blocked) | `mojeek`, `brave`, `ecosia`, `duckduckgo`, `searx` | 4xx / connection-refused. The runner treats these as `NO_RESPONSE` → retry exhaustion. |

Without the user's residential rotating proxies, you can ONLY test:
- 4-5 Tier-B engines for actual URL extraction.
- All other engines for **graceful failure** (no exceptions, no junk URLs in output, blocking-detection path fires).

When the user provides their `proxies.txt`, all 14 engines should produce results. Re-run `Test 4` from `/home/ubuntu/akaza_test_plan.md` against `--proxy-mode file --proxies-file proxies.txt`.

## How CSS selectors rot (and how to catch it)

The v9 engine extractors were originally written against synthetic HTML and broke against real live SERPs. Two engines hit 0 URLs in Test 4 of the test plan: `bing` and `startpage`.

**Symptom:** unit tests pass but live extraction returns 0 URLs from a 200 OK SERP.

**Diagnosis workflow:**

1. Probe each engine and save the actual HTML:
   ```python
   from akaza.http import fetch
   from akaza.config import Settings
   from akaza.engines import make_engine
   engine = make_engine('bing')
   html = await fetch(engine.build_url('inurl:product.php?id=', 0),
                      engine='bing', settings=Settings(), proxy=None)
   open('/tmp/serp_bing.html','w').write(html)
   ```
2. Inspect with BeautifulSoup, looking for stable class names that don't have content-hash suffixes:
   ```python
   from bs4 import BeautifulSoup
   soup = BeautifulSoup(open('/tmp/serp_bing.html').read(), 'html.parser')
   for sel in ('a.tilk[href]', 'a.result-title[href]', 'a.wgl-display-url[href]'):
       hits = soup.select(sel)
       print(f'{sel}: {len(hits)} hits, sample: {hits[0].get("href")[:90] if hits else None}')
   ```
3. Add a regression fixture in `tests/fixtures/serp/` with the captured HTML, plus a test in `tests/test_engines_live_fixtures.py` that asserts `engine.extract(html)` returns at least N URLs and none of them are the engine's own homepage.

**Known fragile patterns to watch for:**
- **Bing**: results are `a.tilk[href]` redirecting through `bing.com/ck/a?u=...`. Do NOT filter `bing.com` hrefs in the extractor — the `cleaner.unwrap_redirect()` step decodes them.
- **Startpage**: modern theme uses Emotion-style class names like `result-title css-1bggj8v` where `css-XXXXX` rotates with every Startpage deploy. Anchor on the stable parts (`result-title`, `result-link`, `wgl-display-url`, `wgl-site-title`, `favicon-link`).
- **Qwant**: SERP HTML is JS-rendered; static HTTP returns a skeleton with no web-result data. Extractor relies on regex backstop and may always be low-yield.
- **Marginalia**: doesn't support Google operators (`inurl:`, `intitle:`). Use plain text queries.
- **Google**: from a datacenter IP, returns interstitial bounce page (`"Please click here if you are not redirected"`). Already in `blocked_phrases`.

## Dork suffix filter end-to-end check

The `apply_dork_suffix` flag is parsed from the dork string `query .ext?param=`. It's BOTH a hard filter (URLs must match `.ext` AND `?param=` shape) AND a +0.30 scorer signal. This is the most common cause of "v8 returned trash" — bad dorks parsed as no suffix → nothing filtered.

Verify with offline test:
```python
from akaza.dorks import parse_dork
d = parse_dork('Membresía VIP .htm?cat=')
assert d.query == 'Membresía VIP'
assert d.ext == 'htm' and d.param == 'cat'
assert d.matches('https://shop.example.com/category.htm?cat=10') is True
assert d.matches('https://shop.example.com/category.htm?id=10') is False
```

## Proxy pool gotcha

`ProxyManager._is_residential` is a pool-level flag (True if ANY proxy in the pool matches the residential pattern). It controls things like skipping bulk validation. **It must NOT control banning** — ban behaviour is per-proxy.

Verify with mixed-pool test:
```python
pm.load_from_list(['1.1.1.1:80', '2.2.2.2:80', 'user:pass@gate.smartproxy.com:7000'])
assert pm.is_residential is True
pm.ban('http://1.1.1.1:80', seconds=300)
seen = {pm.next_proxy() for _ in range(12)}
assert 'http://1.1.1.1:80' not in seen   # regular proxy IS banned
assert 'http://user:pass@gate.smartproxy.com:7000' in seen   # gateway is sticky
```

The regression test for this is `test_mixed_pool_bans_only_regular_proxies` in `tests/test_proxies.py`.

## Full 8-test plan

The full test plan with concrete pass/fail thresholds lives at `/home/ubuntu/akaza_test_plan.md` after `enter_test_mode`. Eight tests covering: unit suite · CLI surface · dork suffix offline · live Tier-B extraction · live Tier-C blocking · suffix filter end-to-end · quality threshold sweep · proxy file pipeline.

## Setup commands

```bash
pip install -r requirements.txt
pip install ruff pytest
python -c "from curl_cffi import requests"   # confirm curl_cffi importable
```

If curl_cffi import fails, the runner falls back to aiohttp (use `--no-curl-cffi`). Block rate on Google/Bing/Yahoo will spike without curl_cffi.

## CI status

This repo has **no CI configured**. `git_pr_checks` returns 0 pending / 0 passed / 0 failed. Don't wait on CI.

## Devin secrets needed

- None for offline tests.
- For live Google/Bing/Yahoo extraction at scale: residential rotating proxies (provided by user as `proxies.txt`, NOT stored as a Devin secret).
