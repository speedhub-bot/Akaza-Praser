"""Unit tests for ``akaza.quality``."""

from __future__ import annotations

from akaza.dorks import parse_dork
from akaza.quality import score_url


def test_dork_match_boosts_score():
    dork = parse_dork("test .php?id=")
    high = score_url("https://shop.example.com/product.php?id=1", dork)
    low = score_url("https://shop.example.com/about.html", dork)
    assert high > low
    assert high > 0.7


def test_signal_extension_increases_score():
    dork = parse_dork("foo")
    php = score_url("https://example.com/index.php", dork)
    plain = score_url("https://example.com/index", dork)
    assert php > plain


def test_homepage_penalised():
    dork = parse_dork("foo")
    home = score_url("https://example.com/", dork)
    deep = score_url("https://example.com/category/item.php?id=10", dork)
    assert deep > home


def test_low_quality_host_penalised():
    dork = parse_dork("foo")
    medium = score_url("https://medium.com/post-title", dork)
    other = score_url("https://shop.example.com/post-title", dork)
    assert medium < other


def test_query_string_increases_score():
    dork = parse_dork("foo")
    with_q = score_url("https://example.com/page?id=1", dork)
    without_q = score_url("https://example.com/page", dork)
    assert with_q > without_q


def test_score_in_unit_interval():
    dork = parse_dork("foo .php?id=")
    for url in (
        "https://shop.example.com/product.php?id=1",
        "https://example.com/",
        "https://medium.com/x",
        "https://example.com/category/item",
        "",
    ):
        s = score_url(url, dork)
        assert 0.0 <= s <= 1.0


def test_inurl_operator_boost():
    dork = parse_dork("inurl:admin login")
    boosted = score_url("https://example.com/admin/login.php", dork)
    plain = score_url("https://example.com/account/profile.php", dork)
    assert boosted > plain


def test_blog_tag_path_penalised():
    dork = parse_dork("foo")
    tag = score_url("https://blog.example.com/category/news", dork)
    article = score_url("https://blog.example.com/article.php?id=5", dork)
    assert article > tag
