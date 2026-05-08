"""Unit tests for ``akaza.proxies`` — local logic only (no network)."""

from __future__ import annotations

import time

from akaza.proxies import ProxyManager


def test_load_from_list_sets_count():
    pm = ProxyManager()
    pm.load_from_list(["1.2.3.4:8080", "5.6.7.8:3128"], protocol="http")
    assert pm.count == 2
    assert pm.protocol == "http"


def test_next_proxy_format():
    pm = ProxyManager()
    pm.load_from_list(["1.2.3.4:8080"], protocol="http")
    assert pm.next_proxy() == "http://1.2.3.4:8080"


def test_round_robin_rotation():
    pm = ProxyManager()
    pm.load_from_list(["1.1.1.1:80", "2.2.2.2:80", "3.3.3.3:80"], protocol="http")
    seen = [pm.next_proxy() for _ in range(6)]
    # Each proxy returned at least twice (round-robin over 3 over 6 calls)
    assert seen.count("http://1.1.1.1:80") == 2
    assert seen.count("http://2.2.2.2:80") == 2
    assert seen.count("http://3.3.3.3:80") == 2


def test_ban_skips_banned_proxy():
    pm = ProxyManager()
    pm.load_from_list(["1.1.1.1:80", "2.2.2.2:80"], protocol="http")
    pm.ban("http://1.1.1.1:80", seconds=60)
    seen = {pm.next_proxy() for _ in range(4)}
    assert "http://2.2.2.2:80" in seen
    # The banned one shouldn't be in the rotation while ban is active
    assert "http://1.1.1.1:80" not in seen


def test_residential_detection():
    pm = ProxyManager()
    pm.load_from_list(
        ["user:pass@gate.smartproxy.com:7000"],
        protocol="http",
    )
    assert pm.is_residential is True


def test_residential_not_banned():
    pm = ProxyManager()
    pm.load_from_list(
        ["user:pass@resi-rotating.example.com:8000"],
        protocol="http",
    )
    proxy = pm.next_proxy()
    pm.ban(proxy, seconds=300)
    # Residential gateways are never actually banned
    assert pm.next_proxy() == proxy


def test_mixed_pool_bans_only_regular_proxies():
    """Per-proxy ban check: a residential gateway in the pool must NOT
    grant immunity to regular proxies in the same pool."""
    pm = ProxyManager()
    pm.load_from_list(
        [
            "1.1.1.1:80",  # regular, MUST be bannable
            "2.2.2.2:80",  # regular, MUST be bannable
            "user:pass@gate.smartproxy.com:7000",  # residential, never banned
        ],
        protocol="http",
    )
    assert pm.is_residential is True  # pool-level flag still set

    # Ban a regular proxy.
    pm.ban("http://1.1.1.1:80", seconds=300)
    seen = {pm.next_proxy() for _ in range(12)}
    assert "http://1.1.1.1:80" not in seen, \
        "regular proxy ban was silently ignored because pool contained a resi entry"
    assert "http://2.2.2.2:80" in seen
    assert "http://user:pass@gate.smartproxy.com:7000" in seen

    # The residential gateway is still immune to banning even after attempt.
    pm.ban("http://user:pass@gate.smartproxy.com:7000", seconds=300)
    seen2 = {pm.next_proxy() for _ in range(12)}
    assert "http://user:pass@gate.smartproxy.com:7000" in seen2


def test_ban_expires():
    pm = ProxyManager()
    pm.load_from_list(["1.1.1.1:80"], protocol="http")
    pm.ban("http://1.1.1.1:80", seconds=0.01)
    time.sleep(0.05)
    # After expiry, the proxy is returned again
    assert pm.next_proxy() == "http://1.1.1.1:80"


def test_clear_resets_state():
    pm = ProxyManager()
    pm.load_from_list(["1.1.1.1:80"], protocol="http")
    pm.clear()
    assert pm.count == 0
    assert pm.next_proxy() is None


def test_pre_formatted_proxy_passthrough():
    pm = ProxyManager()
    pm.load_from_list(
        ["socks5://user:pass@proxy.example.com:1080"],
        protocol="socks5",
    )
    assert pm.next_proxy() == "socks5://user:pass@proxy.example.com:1080"
