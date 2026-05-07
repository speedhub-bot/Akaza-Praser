"""Unit tests for ``akaza.dorks``."""

from __future__ import annotations

from akaza.dorks import Dork, parse_dork, parse_dorks


class TestParseDork:
    def test_legacy_suffix_with_param(self):
        d = parse_dork("Membresía VIP .htm?cat=")
        assert d.query == "Membresía VIP"
        assert d.ext == "htm"
        assert d.param == "cat"
        assert not d.operators

    def test_legacy_suffix_without_param(self):
        d = parse_dork("buy now .php")
        assert d.query == "buy now"
        assert d.ext == "php"
        assert d.param == ""

    def test_aspx_with_login_param(self):
        d = parse_dork("login portal .aspx?login_id=")
        assert d.query == "login portal"
        assert d.ext == "aspx"
        assert d.param == "login_id"

    def test_no_suffix(self):
        d = parse_dork("contoh kalimat indonesia")
        assert d.query == "contoh kalimat indonesia"
        assert d.ext == ""
        assert d.param == ""

    def test_dork_with_inurl_operator_passthrough(self):
        d = parse_dork("inurl:index.php?id=")
        assert d.operators is True
        assert d.query == "inurl:index.php?id="

    def test_dork_with_site_operator_passthrough(self):
        d = parse_dork("site:example.com login")
        assert d.operators is True
        assert d.query == "site:example.com login"

    def test_dork_with_filetype_operator_passthrough(self):
        d = parse_dork("filetype:pdf budget")
        assert d.operators is True

    def test_blank_lines_are_dropped(self):
        out = parse_dorks(["", "   ", "valid .php?id="])
        assert len(out) == 1
        assert out[0].query == "valid"


class TestDorkMatches:
    def test_operator_dorks_match_anything(self):
        d = Dork(raw="x", query="inurl:foo", operators=True)
        assert d.matches("https://random.example.com/")

    def test_no_filter_matches_anything(self):
        d = Dork(raw="x", query="hello")
        assert d.matches("https://random.example.com/page")

    def test_ext_filter_pass(self):
        d = parse_dork("foo .php?id=")
        assert d.matches("https://shop.example.com/index.php?id=10")

    def test_ext_filter_fail_when_extension_differs(self):
        d = parse_dork("foo .php?id=")
        assert not d.matches("https://shop.example.com/about.html?id=10")

    def test_param_filter_fail_when_param_missing(self):
        d = parse_dork("foo .php?id=")
        assert not d.matches("https://shop.example.com/page.php?cat=10")

    def test_htm_html_lenient_match(self):
        d = parse_dork("foo .htm?cat=")
        # HTML should also match when dork specified .htm
        assert d.matches("https://shop.example.com/page.html?cat=1")
        assert d.matches("https://shop.example.com/page.htm?cat=1")
