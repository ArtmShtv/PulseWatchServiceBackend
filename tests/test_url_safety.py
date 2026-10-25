import ipaddress
import socket

import pytest
import requests

from app.core import url_safety
from app.core.url_safety import UnsafeTargetError, check_url_host, ensure_public_target
from app.schemas.monitor_schemas import MonitorCreateSchema, MonitorUpdateSchema
from app.tasks import tasks


def fake_dns(mapping: dict[str, str]):
    """getaddrinfo replacement: hostname -> single IP."""

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror("Name or service not known")
        ip = mapping[host]
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (ip, port))]

    return getaddrinfo


class FakeResponse:
    def __init__(self, status_code: int, location: str | None = None):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}
        self.is_redirect = location is not None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def requests_log(monkeypatch):
    """Replace requests.request in the worker; responses are set per URL."""
    log: list[str] = []
    responses: dict[str, FakeResponse] = {}

    def fake_request(method, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        log.append(url)
        return responses[url]

    monkeypatch.setattr(tasks.requests, "request", fake_request)
    return log, responses


# ---------- is_public_ip ----------

@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",        # loopback
        "10.1.2.3",         # private
        "172.18.0.5",       # private (Docker networks)
        "192.168.1.1",      # private
        "169.254.169.254",  # link-local: cloud metadata
        "100.64.0.1",       # carrier-grade NAT
        "0.0.0.0",
        "224.0.0.1",        # multicast
        "::1",
        "fd00::1",          # IPv6 unique local
        "fe80::1",          # IPv6 link-local
        "::ffff:127.0.0.1", # IPv4-mapped loopback
    ],
)
def test_non_public_ips(ip):
    assert url_safety.is_public_ip(ipaddress.ip_address(ip)) is False


@pytest.mark.parametrize("ip", ["93.184.215.14", "8.8.8.8", "2606:4700:4700::1111"])
def test_public_ips(ip):
    assert url_safety.is_public_ip(ipaddress.ip_address(ip)) is True


# ---------- check_url_host (no DNS, used by the API) ----------

@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/users",
        "http://LOCALHOST/",
        "http://api.localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/admin",
        "http://[::1]:8000/",
    ],
)
def test_check_url_host_rejects_internal(url):
    with pytest.raises(UnsafeTargetError):
        check_url_host(url)


@pytest.mark.parametrize("url", ["https://example.com/", "http://8.8.8.8/", "http://postgres:5432"])
def test_check_url_host_allows_public_or_unresolved(url):
    # hostnames like "postgres" are only caught after DNS, in the worker
    check_url_host(url)


def test_allow_private_targets_setting(monkeypatch):
    monkeypatch.setattr(url_safety.settings, "ALLOW_PRIVATE_TARGETS", True)

    check_url_host("http://localhost/")
    ensure_public_target("http://127.0.0.1/")


# ---------- ensure_public_target (DNS, used by the worker) ----------

def test_hostname_resolving_to_private_ip_is_blocked(monkeypatch):
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({"postgres": "172.18.0.2"}))

    with pytest.raises(UnsafeTargetError, match="172.18.0.2"):
        ensure_public_target("http://postgres:5432")


def test_hostname_resolving_to_public_ip_is_allowed(monkeypatch):
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({"example.com": "93.184.215.14"}))

    ensure_public_target("https://example.com/")


# ---------- schemas ----------

def test_create_schema_rejects_internal_url():
    with pytest.raises(ValueError, match="localhost"):
        MonitorCreateSchema(name="x", url="http://localhost:8000", interval_seconds=60, timeout_seconds=5)


def test_update_schema_rejects_internal_url():
    with pytest.raises(ValueError, match="169.254.169.254"):
        MonitorUpdateSchema(url="http://169.254.169.254/")


async def test_api_rejects_internal_url(client):
    await client.post(
        "/users/register",
        json={"email": "s@example.com", "username": "ssrf", "password": "strongpass123"},
    )
    token = (
        await client.post("/users/login", json={"email": "s@example.com", "password": "strongpass123"})
    ).json()["access_token"]

    resp = await client.post(
        "/monitors/",
        json={"name": "x", "url": "http://127.0.0.1:6379", "interval_seconds": 60, "timeout_seconds": 5},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 422


# ---------- probe (worker) ----------

def test_probe_blocks_private_target_without_sending_request(monkeypatch, requests_log):
    log, _ = requests_log
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({"redis": "172.18.0.3"}))

    result = tasks.probe("GET", "http://redis:6379", 5, 200)

    assert result.is_up is False
    assert result.error.startswith("Blocked:")
    assert log == []


def test_probe_follows_public_redirect(monkeypatch, requests_log):
    log, responses = requests_log
    monkeypatch.setattr(
        url_safety.socket, "getaddrinfo",
        fake_dns({"example.com": "93.184.215.14", "www.example.com": "93.184.215.15"}),
    )
    responses["http://example.com/"] = FakeResponse(301, location="https://www.example.com/")
    responses["https://www.example.com/"] = FakeResponse(200)

    result = tasks.probe("GET", "http://example.com/", 5, 200)

    assert result.is_up is True
    assert log == ["http://example.com/", "https://www.example.com/"]


def test_probe_blocks_redirect_to_private_address(monkeypatch, requests_log):
    log, responses = requests_log
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({"evil.example": "93.184.215.14"}))
    responses["http://evil.example/"] = FakeResponse(302, location="http://169.254.169.254/latest/meta-data/")

    result = tasks.probe("GET", "http://evil.example/", 5, 200)

    assert result.is_up is False
    assert "169.254.169.254" in result.error
    assert log == ["http://evil.example/"]  # the metadata endpoint was never requested


def test_probe_stops_redirect_loops(monkeypatch, requests_log):
    _, responses = requests_log
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({"loop.example": "93.184.215.14"}))
    responses["http://loop.example/"] = FakeResponse(302, location="/")

    result = tasks.probe("GET", "http://loop.example/", 5, 200)

    assert result.is_up is False
    assert result.error == "Request error: TooManyRedirects"


def test_probe_reports_dns_failure(monkeypatch, requests_log):
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({}))

    result = tasks.probe("GET", "http://does-not-exist.example/", 5, 200)

    assert result == tasks.ProbeResult(False, error="DNS resolution failed")


def test_probe_timeout(monkeypatch):
    monkeypatch.setattr(url_safety.socket, "getaddrinfo", fake_dns({"slow.example": "93.184.215.14"}))

    def timeout(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(tasks.requests, "request", timeout)

    result = tasks.probe("GET", "http://slow.example/", 3, 200)

    assert result.error == "Timed out after 3s"
