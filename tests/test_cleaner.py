"""Unit tests for ``akaza.cleaner``."""

from __future__ import annotations

import base64
import urllib.parse

from akaza import cleaner


class TestUnwrapRedirect:
    def test_duckduckgo_uddg(self):
        target = "https://example.com/foo?bar=1"
        wrapped = (
            "//duckduckgo.com/l/?uddg="
            + urllib.parse.quote(target, safe="")
            + "&rut=abc"
        )
        assert cleaner.clean(wrapped) == target

    def test_google_url_q(self):
        target = "https://example.com/post"
        url = "https://www.google.com/url?q=" + urllib.parse.quote(target, safe="")
        assert cleaner.clean(url) == target

    def test_yahoo_ru(self):
        target = "https://www.example.com/page"
        wrapped = "https://r.search.yahoo.com/_ylt=A0/RU=" + urllib.parse.quote(target, safe="") + "/RK=2/RS=foo"
        assert cleaner.clean(wrapped) == target

    def test_bing_ck_a_base64(self):
        target = "https://www.example.com/path"
        b64 = base64.b64encode(target.encode()).decode()
        b64 = b64.replace("+", "-").replace("/", "_").rstrip("=")
        url = f"https://www.bing.com/ck/a?u=a1{b64}&ntb=1"
        assert cleaner.clean(url) == target


class TestStripTracking:
    def test_strip_utm(self):
        out = cleaner.strip_tracking(
            "https://example.com/p?id=10&utm_source=newsletter&utm_medium=email"
        )
        assert "utm_" not in out
        assert "id=10" in out

    def test_strip_gclid_fbclid(self):
        out = cleaner.strip_tracking(
            "https://example.com/p?id=10&gclid=abc&fbclid=def"
        )
        assert "gclid" not in out
        assert "fbclid" not in out
        assert "id=10" in out

    def test_no_tracking_keeps_url_intact(self):
        out = cleaner.strip_tracking("https://example.com/path?a=1&b=2")
        # Order may not be preserved but params must be present
        parsed = urllib.parse.urlparse(out)
        assert parsed.path == "/path"
        assert dict(urllib.parse.parse_qsl(parsed.query)) == {"a": "1", "b": "2"}


class TestNormalise:
    def test_drops_www_lowers_scheme(self):
        assert cleaner.normalise("HTTPS://WWW.Example.com/Foo/") == \
            "https://example.com/Foo"

    def test_sorts_query(self):
        a = cleaner.normalise("https://x.com/p?z=1&a=2")
        b = cleaner.normalise("https://x.com/p?a=2&z=1")
        assert a == b

    def test_strips_fragment(self):
        assert cleaner.normalise("https://x.com/p#section") == "https://x.com/p"


class TestClean:
    def test_pipeline_unquotes_unwraps_strips_tracking(self):
        target = "https://example.com/a?b=1"
        url = (
            "https://www.google.com/url?q="
            + urllib.parse.quote(target, safe="")
            + "&utm_source=ads"
        )
        out = cleaner.clean(url)
        assert out.startswith("https://example.com/a")
        assert "utm_source" not in out

    def test_strips_trailing_punctuation(self):
        assert cleaner.clean("https://example.com/foo).") == "https://example.com/foo"
