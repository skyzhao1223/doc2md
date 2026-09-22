"""SSRF-protection tests for URL validation (no real network access)."""

from __future__ import annotations

import socket

import pytest

from doc2md import fetch


def test_rejects_loopback():
    with pytest.raises(fetch.FetchError, match="Refusing"):
        fetch.validate_url("http://127.0.0.1/secret.pdf")


def test_rejects_cloud_metadata_endpoint():
    with pytest.raises(fetch.FetchError, match="Refusing"):
        fetch.validate_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_private_ranges():
    for url in (
        "http://10.0.0.5/a.pdf",
        "http://192.168.1.1/a.pdf",
        "http://[::1]/a.pdf",
    ):
        with pytest.raises(fetch.FetchError, match="Refusing"):
            fetch.validate_url(url)


def test_rejects_bad_schemes():
    with pytest.raises(fetch.FetchError, match="not allowed"):
        fetch.validate_url("ftp://example.com/file.pdf")
    with pytest.raises(fetch.FetchError):
        fetch.validate_url("file:///etc/passwd")


def test_rejects_hostname_resolving_to_private_ip(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 80))]

    monkeypatch.setattr(fetch.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(fetch.FetchError, match="Refusing"):
        fetch.validate_url("http://evil.example.com/file.pdf")


def test_allows_public_hostname(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(fetch.socket, "getaddrinfo", fake_getaddrinfo)
    fetch.validate_url("https://example.com/report.pdf")  # must not raise
