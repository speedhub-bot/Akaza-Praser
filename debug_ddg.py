"""Check DDG and Bing raw HTML structure to fix extractors."""
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
    query = "Membresía VIP"
    enc = urllib.parse.quote_plus(query)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as session:
        # DuckDuckGo - check structure
        ddg_url = f"https://html.duckduckgo.com/html/?q={enc}"
        async with session.get(ddg_url, ssl=False) as r:
            html = await r.text()
        # Look for result URLs in various places
        # DDG html uses value="..." in hidden inputs for redirects
        vals = re.findall(r'value="(https?://[^"]+)"', html)
        forms = re.findall(r'action="([^"]+)"', html)
        snippets = re.findall(r'class="result__url"[^>]*>(.*?)</span>', html, re.S)
        spans = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', html)
        uddg = re.findall(r'uddg=(https?[^&"<>\s]+)', html)

        with open("ddg_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        print(f"DDG status={r.status} | size={len(html)}")
        print(f"  value= URLs: {vals[:5]}")
        print(f"  action= URLs: {forms[:5]}")
        print(f"  result__url spans: {snippets[:5]}")
        print(f"  result__a hrefs: {spans[:5]}")
        print(f"  uddg= URLs: {uddg[:5]}")

        # Try to find ANY result links
        all_links = re.findall(r'(https?://(?!.*duckduckgo\.com)[^\s"\'<>]{15,})', html)
        print(f"  Any real links in html: {all_links[:10]}")
        print()

asyncio.run(debug())
