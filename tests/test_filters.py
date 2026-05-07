"""Unit tests for ``akaza.filters``."""

from __future__ import annotations

from akaza.filters import URLFilter, URLStore


class TestURLFilter:
    def test_blocks_youtube(self):
        f = URLFilter()
        assert not f.is_valid("https://www.youtube.com/watch?v=abc")

    def test_blocks_google(self):
        f = URLFilter()
        assert not f.is_valid("https://www.google.com/search?q=abc")

    def test_blocks_bing(self):
        f = URLFilter()
        assert not f.is_valid("https://www.bing.com/search?q=abc")

    def test_allows_random_site(self):
        f = URLFilter()
        assert f.is_valid("https://random-store.example.com/product.php?id=1")

    def test_blocks_image_extensions(self):
        f = URLFilter()
        assert not f.is_valid("https://shop.example.com/banner.jpg")

    def test_php_only_filter(self):
        f = URLFilter(php_only=True)
        assert f.is_valid("https://shop.example.com/index.php")
        assert not f.is_valid("https://shop.example.com/index.html")

    def test_require_query_filter(self):
        f = URLFilter(require_query=True)
        assert f.is_valid("https://shop.example.com/p?id=1")
        assert not f.is_valid("https://shop.example.com/p")


class TestURLStore:
    def test_dedup_normalises_www(self):
        store = URLStore()
        assert store.add("https://www.example.com/page")
        assert not store.add("https://example.com/page")

    def test_dedup_normalises_query_order(self):
        store = URLStore()
        assert store.add("https://example.com/p?a=1&b=2")
        assert not store.add("https://example.com/p?b=2&a=1")

    def test_unique_sites_only(self):
        store = URLStore(unique_site_only=True)
        assert store.add("https://example.com/page1")
        assert not store.add("https://example.com/page2")
        # Different host still allowed
        assert store.add("https://other.com/page1")

    def test_count(self):
        store = URLStore()
        for i in range(5):
            store.add(f"https://example.com/{i}")
        assert len(store) == 5

    def test_contains(self):
        store = URLStore()
        store.add("https://example.com/x")
        assert "https://example.com/x" in store
        assert "https://nope.com/x" not in store
