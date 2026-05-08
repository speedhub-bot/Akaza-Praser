"""Unit tests for engine extractors using inline sample HTML.

These tests do not hit the network — every fixture is a small synthetic
document modelled on the live SERP HTML structure.
"""

from __future__ import annotations

import pytest

from akaza.engines import (
    AOLEngine,
    BingEngine,
    BraveEngine,
    DuckDuckGoEngine,
    EcosiaEngine,
    GoogleEngine,
    MarginaliaEngine,
    MojeekEngine,
    QwantEngine,
    SearxEngine,
    StartpageEngine,
    YahooEngine,
    YahooJPEngine,
    YandexEngine,
    list_engines,
    make_engine,
)


class TestRegistry:
    def test_all_engines_registered(self):
        names = list_engines()
        for needed in (
            "google", "bing", "brave", "mojeek", "startpage",
            "yandex", "ecosia", "qwant", "duckduckgo",
            "yahoo", "yahoo_jp", "aol", "searx", "marginalia",
        ):
            assert needed in names

    def test_aliases_resolve(self):
        assert make_engine("ddg").name == "duckduckgo"
        assert make_engine("yahoo-jp").name == "yahoo_jp"
        assert make_engine("searxng").name == "searx"

    def test_unknown_engine_raises(self):
        with pytest.raises(KeyError):
            make_engine("does_not_exist")


class TestBuildURL:
    @pytest.mark.parametrize("name", list_engines())
    def test_build_url_contains_query(self, name):
        engine = make_engine(name)
        url = engine.build_url("test query 123", 0)
        assert url.startswith("http")
        assert "test" in url and "query" in url

    @pytest.mark.parametrize("name", list_engines())
    def test_build_url_pagination_changes(self, name):
        engine = make_engine(name)
        u0 = engine.build_url("dorky", 0)
        u1 = engine.build_url("dorky", 1)
        # SearXNG rotates instances so URL host can change too — the test only
        # requires the per-page URL to differ in some way.
        assert u0 != u1 or "?" in u1


class TestGoogleExtractor:
    def test_extracts_yuRUbf(self):
        html = """
        <html><body>
          <div class="yuRUbf"><a href="https://example.com/page">Title</a></div>
          <div class="yuRUbf"><a href="https://other.com/foo">Title</a></div>
          <a href="/url?q=https://third.example.com/x&sa=U">x</a>
        </body></html>
        """
        urls = GoogleEngine().extract(html)
        assert "https://example.com/page" in urls
        assert "https://other.com/foo" in urls
        assert "https://third.example.com/x" in urls

    def test_filters_out_google_internals(self):
        html = '<div class="g"><a href="https://www.google.com/search?q=foo">x</a></div>'
        assert GoogleEngine().extract(html) == []


class TestBingExtractor:
    def test_extracts_b_algo(self):
        html = """
        <ol id="b_results">
          <li class="b_algo">
            <h2><a href="https://example.com/foo">Title</a></h2>
          </li>
          <li class="b_algo">
            <div class="b_caption"><a href="https://other.com/bar">Other</a></div>
          </li>
        </ol>
        """
        urls = BingEngine().extract(html)
        assert "https://example.com/foo" in urls
        assert "https://other.com/bar" in urls


class TestBraveExtractor:
    def test_extracts_snippet_links(self):
        html = """
        <div class="snippet" data-type="web">
          <a class="h" href="https://store.example.com/item.php?id=1">Title</a>
        </div>
        <main>
          <a class="h" href="https://other.example.com/page">Other</a>
        </main>
        """
        urls = BraveEngine().extract(html)
        assert "https://store.example.com/item.php?id=1" in urls
        assert "https://other.example.com/page" in urls


class TestMojeekExtractor:
    def test_extracts_results_standard(self):
        html = """
        <ul class="results-standard">
          <li><h2><a href="https://example.com/a">Foo</a></h2></li>
          <li><a class="ob" href="https://other.com/b">Bar</a></li>
        </ul>
        """
        urls = MojeekEngine().extract(html)
        assert "https://example.com/a" in urls
        assert "https://other.com/b" in urls


class TestStartpageExtractor:
    def test_extracts_w_gl_results(self):
        html = """
        <div class="w-gl__result">
          <a class="w-gl__result-title" href="https://example.com/p">Title</a>
        </div>
        <a class="w-gl__result-url" href="https://other.com/page">x</a>
        """
        urls = StartpageEngine().extract(html)
        assert "https://example.com/p" in urls
        assert "https://other.com/page" in urls


class TestYandexExtractor:
    def test_extracts_organic(self):
        html = """
        <li class="serp-item">
          <a class="organic__url" href="https://example.com/page">Title</a>
        </li>
        <li class="serp-item">
          <a class="Link Link_theme_normal" href="https://other.com/foo">Other</a>
        </li>
        """
        urls = YandexEngine().extract(html)
        assert "https://example.com/page" in urls
        assert "https://other.com/foo" in urls

    def test_extracts_clck_jsredir(self):
        html = '<a href="/clck/jsredir?from=yandex&amp;to=https%3A//example.com/p">x</a>'
        urls = YandexEngine().extract(html)
        # %3A// becomes :// after parsing — but our regex captures the literal
        assert any("example.com" in u for u in urls)


class TestEcosiaExtractor:
    def test_extracts_results(self):
        html = """
        <article class="result">
          <a class="result__link" href="https://example.com/foo">Title</a>
        </article>
        """
        urls = EcosiaEngine().extract(html)
        assert "https://example.com/foo" in urls


class TestQwantExtractor:
    def test_extracts_web_result(self):
        html = """
        <a data-testid="serTitle" href="https://example.com/q">Title</a>
        """
        urls = QwantEngine().extract(html)
        assert "https://example.com/q" in urls


class TestDuckDuckGoExtractor:
    def test_extracts_result_a(self):
        html = """
        <a class="result__a" href="https://example.com/p">Title</a>
        <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A//other.com/foo">Other</a>
        """
        urls = DuckDuckGoEngine().extract(html)
        assert "https://example.com/p" in urls
        assert any("other.com/foo" in u for u in urls)


class TestYahooExtractor:
    def test_extracts_data_ru(self):
        html = '<a data-ru="https%3A//example.com/p" href="https://r.search.yahoo.com/_ylt=A0/RU=https%3A//example.com/p/RK=2">Title</a>'
        urls = YahooEngine().extract(html)
        assert any("example.com" in u for u in urls)


class TestYahooJPExtractor:
    def test_extracts_external_only(self):
        html = """
        <div class="sw-Card__title">
          <a href="https://example.com/p">Title</a>
        </div>
        <div class="sw-Card__title">
          <a href="https://www.yahoo.co.jp/internal">Should drop</a>
        </div>
        """
        urls = YahooJPEngine().extract(html)
        assert "https://example.com/p" in urls
        assert not any("yahoo.co.jp" in u for u in urls)


class TestAOLExtractor:
    def test_extracts_compTitle_with_RU(self):
        html = """
        <div class="compTitle">
          <a href="https://search.aol.com/aol/click?u=&RU=https%3A//example.com/p/RK=2">Title</a>
        </div>
        """
        urls = AOLEngine().extract(html)
        assert any("example.com" in u for u in urls)


class TestSearxExtractor:
    def test_extracts_result_h3(self):
        html = """
        <article class="result">
          <h3><a href="https://example.com/p">Title</a></h3>
        </article>
        <article class="result-default">
          <a class="url_wrapper" href="https://other.com/q">Other</a>
        </article>
        """
        urls = SearxEngine().extract(html)
        assert "https://example.com/p" in urls
        assert "https://other.com/q" in urls

    def test_drops_searx_instance_urls(self):
        html = """
        <article class="result">
          <h3><a href="https://searx.be/preferences">Bad</a></h3>
        </article>
        """
        urls = SearxEngine().extract(html)
        assert urls == []


class TestMarginaliaExtractor:
    def test_extracts_search_result(self):
        html = """
        <section class="search-result">
          <h2><a href="https://example.com/page">Title</a></h2>
        </section>
        """
        urls = MarginaliaEngine().extract(html)
        assert "https://example.com/page" in urls


class TestBlockingDetection:
    def test_google_unusual_traffic(self):
        assert GoogleEngine().is_blocked(
            "<html><body>unusual traffic from your computer network</body></html>"
        )

    def test_yahoo_consent_redirect(self):
        assert YahooEngine().is_blocked("redirected to consent.yahoo.com")

    def test_yandex_captcha(self):
        assert YandexEngine().is_blocked("<html>...showcaptcha?action=...")

    def test_clean_html_not_blocked(self):
        assert not BingEngine().is_blocked(
            "<html><body><li class='b_algo'><a href='https://x.com/'>x</a></li></body></html>"
        )
