import httpx
import pytest
import respx

from orchestrator.api_client import ApiClient
from orchestrator.config import Settings
from orchestrator.scan_worker_client import ScanWorkerClient


def _settings():
    return Settings(
        INTERNAL_SERVICE_TOKEN="test-token",
        API_INTERNAL_URL="http://api.test",
        SCAN_WORKER_INTERNAL_URL="http://worker.test",
    )


@pytest.mark.asyncio
@respx.mock
async def test_api_client_sends_service_token_header():
    route = respx.get("http://api.test/scans/pending").mock(return_value=httpx.Response(200, json=[]))
    client = ApiClient(_settings())
    result = await client.list_pending_scans()
    assert result == []
    assert route.calls.last.request.headers["x-service-token"] == "test-token"


@pytest.mark.asyncio
@respx.mock
async def test_api_client_create_approval_posts_expected_body():
    route = respx.post("http://api.test/approvals").mock(
        return_value=httpx.Response(201, json={"id": "a1", "status": "pending"})
    )
    client = ApiClient(_settings())
    result = await client.create_approval(
        scan_id="s1", target_id="t1", category="aggressive_payload", action_description="d"
    )
    assert result["id"] == "a1"
    body = route.calls.last.request.content
    assert b"aggressive_payload" in body


@pytest.mark.asyncio
@respx.mock
async def test_scan_worker_client_run_httpx_success():
    respx.post("http://worker.test/scan/httpx").mock(
        return_value=httpx.Response(200, json={"tool": "httpx", "available": True, "success": True, "results": []})
    )
    client = ScanWorkerClient(_settings())
    result = await client.run_httpx(["https://example.test"])
    assert result["available"] is True


@pytest.mark.asyncio
@respx.mock
async def test_scan_worker_client_degrades_gracefully_on_network_error():
    respx.post("http://worker.test/scan/nmap").mock(side_effect=httpx.ConnectError("refused"))
    client = ScanWorkerClient(_settings())
    result = await client.run_nmap("example.test")
    assert result["available"] is False
    assert "error" in result
