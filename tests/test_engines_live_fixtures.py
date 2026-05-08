"""Regression tests against real captured SERP HTML.

These fixtures are saved snapshots of live SERPs taken during this session.
They lock down the engine extractors against future regressions when SERP
markup changes again.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from akaza import cleaner
from akaza.engines import (
    AOLEngine,
    BingEngine,
    GoogleEngine,
    StartpageEngine,
    YahooEngine,
    YahooJPEngine,
    YandexEngine,
)

FIXTURES = Path(__file__).parent / "fixtures" / "serp"


def _load(name: str) -> str:
    p = FIXTURES / name
    return p.read_text(encoding="utf-8", errors="ignore")


def _clean_all(urls: list[str]) -> list[str]:
    out = []
    for u in urls:
        c = cleaner.clean(u)
        if c and c.startswith("http"):
            out.append(c)
    return out


class TestBingFixture:
    """Bing's modern SERP wraps results in `a.tilk` -> `bing.com/ck/a` redirect."""

    def setup_method(self):
        self.html = _load("bing_inurl_product.html")
        self.engine = BingEngine()

    def test_extracts_at_least_5(self):
        assert len(self.engine.extract(self.html)) >= 5

    def test_no_bing_homepages_after_clean(self):
        cleaned = _clean_all(self.engine.extract(self.html))
        assert cleaned, "no URLs extracted at all"
        for u in cleaned:
            assert "bing.com" not in u, f"unwrapped URL still on bing.com: {u}"

    def test_at_least_one_query_match(self):
        cleaned = _clean_all(self.engine.extract(self.html))
        # The query was `inurl:product.php?id=`. Real results should mention
        # `product.php` somewhere.
        assert any("product.php" in u for u in cleaned), \
            f"no .php product URLs in {cleaned[:5]}"

    def test_blocking_not_falsely_triggered(self):
        assert not self.engine.is_blocked(self.html)


class TestStartpageFixture:
    """Startpage's modern theme uses Emotion class names with rotating hashes."""

    def setup_method(self):
        self.html = _load("startpage_inurl_product.html")
        self.engine = StartpageEngine()

    def test_extracts_at_least_8(self):
        assert len(self.engine.extract(self.html)) >= 8

    def test_no_startpage_homepages(self):
        for u in _clean_all(self.engine.extract(self.html)):
            assert "startpage.com" not in u

    def test_blocking_not_falsely_triggered(self):
        assert not self.engine.is_blocked(self.html)


class TestYahooFixture:
    def setup_method(self):
        self.html = _load("yahoo_inurl_product.html")
        self.engine = YahooEngine()

    def test_extracts_at_least_5(self):
        assert len(self.engine.extract(self.html)) >= 5

    def test_unwraps_RU_redirects(self):
        cleaned = _clean_all(self.engine.extract(self.html))
        assert cleaned
        for u in cleaned:
            assert "r.search.yahoo.com" not in u, \
                f"unwrapping failed: {u}"
            assert "yahoo.com" not in u or u.startswith("https://uk.movies"), \
                f"yahoo internal URL leaked: {u}"


class TestAOLFixture:
    def setup_method(self):
        self.html = _load("aol_inurl_product.html")
        self.engine = AOLEngine()

    def test_extracts_at_least_5(self):
        assert len(self.engine.extract(self.html)) >= 5

    def test_unwraps_RU_redirects(self):
        cleaned = _clean_all(self.engine.extract(self.html))
        assert cleaned
        for u in cleaned:
            assert "search.aol.com" not in u, f"unwrap failed: {u}"


class TestYahooJPFixture:
    def setup_method(self):
        self.html = _load("yahoo_jp_inurl_product.html")
        self.engine = YahooJPEngine()

    def test_extracts_at_least_5(self):
        assert len(self.engine.extract(self.html)) >= 5

    def test_no_yahoo_jp_internal(self):
        for u in self.engine.extract(self.html):
            assert "yahoo.co.jp" not in u


class TestGoogleBlockedFixture:
    """Google returns an interstitial bounce page from datacenter IPs.

    The `extract` path may legitimately return zero URLs from this page;
    the important contract is that ``is_blocked`` recognises it.
    """

    def setup_method(self):
        self.html = _load("google_blocked_interstitial.html")
        self.engine = GoogleEngine()

    def test_blocked_phrase_detected(self):
        assert self.engine.is_blocked(self.html)


class TestYandexCaptchaFixture:
    """Yandex's "Are you not a robot?" captcha page, served to datacenter IPs."""

    def setup_method(self):
        self.html = _load("yandex_captcha.html")
        self.engine = YandexEngine()

    def test_captcha_is_blocked(self):
        assert self.engine.is_blocked(self.html)


@pytest.mark.parametrize("name,engine_cls", [
    ("bing_inurl_product.html", BingEngine),
    ("startpage_inurl_product.html", StartpageEngine),
    ("yahoo_inurl_product.html", YahooEngine),
    ("aol_inurl_product.html", AOLEngine),
    ("yahoo_jp_inurl_product.html", YahooJPEngine),
])
def test_extractor_returns_no_engine_self_links(name, engine_cls):
    """No extractor may return a link to its own engine homepage."""
    html = _load(name)
    engine = engine_cls()
    cleaned = _clean_all(engine.extract(html))
    homepage = engine.homepage.replace("https://", "").replace("http://", "")
    if homepage.startswith("www."):
        homepage = homepage[4:]
    for u in cleaned:
        assert homepage not in u, f"{engine.name} returned own-domain URL: {u}"
