"""Debug: check raw HTML from each engine to understand why 0 results."""
import asyncio
import aiohttp
import random
import urllib.parse
import re
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from akaza import USER_AGENTS, dork_to_query

async def debug():
    dork = "Membresía VIP .htm?cat="
    query = dork_to_query(dork)
    print(f"Original dork: {repr(dork)}")
    print(f"Cleaned query: {repr(query)}")
    print()

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    timeout = aiohttp.ClientTimeout(total=20)

    tests = {
        "Bing": f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}&first=1&setlang=en",
        "Yahoo": f"https://search.yahoo.com/search?p={urllib.parse.quote_plus(query)}&b=1",
        "DuckDuckGo": f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}",
    }

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        for name, url in tests.items():
            try:
                async with session.get(url, ssl=False) as r:
                    html = await r.text()
                    # Check for blocks
                    blocked = ("access denied" in html.lower() or
                               "captcha" in html.lower() or
                               "unusual traffic" in html.lower() or
                               "are you a robot" in html.lower() or
                               "consent.yahoo.com" in html.lower() or
                               "too many requests" in html.lower())
                    # Count href links
                    links = re.findall(r'href="(https?://[^"]{10,})"', html)
                    real = [l for l in links if name.lower() not in l.lower() and
                            "google.com" not in l and "yahoo.com" not in l and
                            "bing.com" not in l and "duckduckgo.com" not in l]
                    print(f"[{name}] Status={r.status} | Blocked={blocked} | HTML_size={len(html)} | All_hrefs={len(links)} | Real_hrefs={len(real)}")
                    if real:
                        for u in real[:5]:
                            print(f"  → {u}")
                    else:
                        # Print snippet
                        snip = html[:1000].replace("\n", " ")
                        print(f"  HTML snippet: {snip[:300]}")
                    print()
            except Exception as e:
                print(f"[{name}] ERROR: {e}")
                print()

asyncio.run(debug())
