import httpx
import pytest
import respx

from orchestrator.config import Settings
from orchestrator.connectors.censys_connector import CensysConnector
from orchestrator.connectors.shodan_connector import ShodanConnector


def _settings(**overrides):
    return Settings(INTERNAL_SERVICE_TOKEN="x", **overrides)


@pytest.mark.asyncio
async def test_shodan_unconfigured_without_api_key():
    connector = ShodanConnector(_settings())
    outcome = await connector.observe("example.test")
    assert outcome.configured is False
    assert outcome.ok is False


@pytest.mark.asyncio
@respx.mock
async def test_shodan_configured_parses_host_data(monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda h: "1.2.3.4")
    respx.get("https://api.shodan.io/shodan/host/1.2.3.4").mock(
        return_value=httpx.Response(
            200,
            json={
                "ports": [80, 443],
                "hostnames": ["example.test"],
                "org": "Example Org",
                "os": None,
                "vulns": [],
            },
        )
    )
    connector = ShodanConnector(_settings(SHODAN_API_KEY="key123"))
    outcome = await connector.observe("example.test")
    assert outcome.configured is True
    assert outcome.ok is True
    assert outcome.data["ports"] == [80, 443]
    assert outcome.data["org"] == "Example Org"


@pytest.mark.asyncio
@respx.mock
async def test_shodan_404_is_ok_but_empty(monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda h: "1.2.3.4")
    respx.get("https://api.shodan.io/shodan/host/1.2.3.4").mock(return_value=httpx.Response(404))
    connector = ShodanConnector(_settings(SHODAN_API_KEY="key123"))
    outcome = await connector.observe("example.test")
    assert outcome.ok is True
    assert outcome.data == {}


@pytest.mark.asyncio
async def test_censys_unconfigured_without_credentials():
    connector = CensysConnector(_settings())
    outcome = await connector.observe("example.test")
    assert outcome.configured is False


@pytest.mark.asyncio
@respx.mock
async def test_censys_configured_parses_host_services(monkeypatch):
    monkeypatch.setattr("socket.gethostbyname", lambda h: "5.6.7.8")
    respx.get("https://search.censys.io/api/v2/hosts/5.6.7.8").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "services": [{"port": 443, "service_name": "HTTPS"}],
                    "autonomous_system": {"name": "Example AS"},
                }
            },
        )
    )
    connector = CensysConnector(_settings(CENSYS_API_ID="id", CENSYS_API_SECRET="secret"))
    outcome = await connector.observe("example.test")
    assert outcome.ok is True
    assert outcome.data["services"] == [{"port": 443, "protocol": "HTTPS"}]
    assert outcome.data["autonomous_system"] == "Example AS"
