"""End-to-end tests for ScanRun: OBSERVE -> REASON -> PLAN -> EXECUTE -> VERIFY
driven against respx-mocked services/api, services/scan-worker, and the
target itself. These are the tests that prove the pieces actually wire
together, not just that each module is individually correct.
"""

import glob
import json
import os

import httpx
import pytest
import respx

from orchestrator.api_client import ApiClient
from orchestrator.config import Settings
from orchestrator.connectors.base import Connector, ConnectorOutcome
from orchestrator.loop import ScanRun
from orchestrator.models import DiscoveredRoute
from orchestrator.ratelimit import CooldownTracker
from orchestrator.scan_worker_client import ScanWorkerClient


class FakeConnector(Connector):
    name = "fake"

    def __init__(self, routes):
        self._routes = routes

    @property
    def configured(self) -> bool:
        return True

    async def observe(self, hostname: str) -> ConnectorOutcome:
        return ConnectorOutcome(self.name, configured=True, ok=True, note="ok", data={"routes": self._routes})


def _settings(tmp_path, **overrides):
    return Settings(
        INTERNAL_SERVICE_TOKEN="test-token",
        API_INTERNAL_URL="http://api.test",
        SCAN_WORKER_INTERNAL_URL="http://worker.test",
        FINDINGS_DIR=str(tmp_path),
        HITL_APPROVAL_TIMEOUT_SECONDS=5,
        **overrides,
    )


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def _mock_common(scan_id: str, approval_id: str, approval_status: str):
    respx.route(method="PATCH", url=f"http://api.test/scans/{scan_id}").mock(
        return_value=httpx.Response(200, json={"id": scan_id, "stage": "x"})
    )
    approvals_route = respx.post("http://api.test/approvals").mock(
        return_value=httpx.Response(201, json={"id": approval_id, "status": "pending"})
    )
    respx.get(f"http://api.test/approvals/{approval_id}").mock(
        return_value=httpx.Response(200, json={"id": approval_id, "status": approval_status})
    )
    findings_route = respx.post("http://api.test/findings").mock(
        return_value=httpx.Response(201, json={"id": "f1"})
    )
    respx.post("http://worker.test/scan/httpx").mock(
        return_value=httpx.Response(
            200, json={"tool": "httpx", "available": False, "success": False, "error": "not installed", "results": []}
        )
    )
    return approvals_route, findings_route


@pytest.mark.asyncio
@respx.mock
async def test_idor_flow_confirmed_and_reported(tmp_path):
    scan = {"id": "s1", "target_id": "t1"}
    target = {
        "id": "t1",
        "name": "demo",
        "base_url": "https://target.test",
        "credentials": {"user_a": {}, "user_b": {}},
        "passive_only": False,
    }
    _approvals_route, findings_route = _mock_common("s1", "appr1", "approved")

    respx.get("https://target.test/api/v1/orders/123").mock(
        return_value=httpx.Response(200, json={"id": "123", "owner": "A"})
    )
    respx.get("https://target.test/api/v1/orders/1231").mock(
        return_value=httpx.Response(200, json={"id": "1231", "owner": "B"})
    )

    settings = _settings(tmp_path)
    api = ApiClient(settings)
    worker = ScanWorkerClient(settings)
    cooldowns = CooldownTracker(60)
    connector = FakeConnector([DiscoveredRoute(method="GET", path="/api/v1/orders/123")])

    run = ScanRun(scan, target, settings, api, worker, cooldowns, connectors=[connector])
    await run.run()

    assert findings_route.call_count == 1
    body = _body(findings_route.calls.last.request)
    assert body["status"] == "confirmed"
    assert body["category"] == "idor"
    assert body["evidence_path"] is not None

    reports = glob.glob(os.path.join(tmp_path, "CONFIRMED_IDOR_DEMO_*.md"))
    assert len(reports) == 1
    content = open(reports[0], encoding="utf-8").read()
    assert "swapped identifier" in content

    await api.aclose()
    await worker.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_idor_flow_skipped_when_approval_rejected(tmp_path):
    scan = {"id": "s2", "target_id": "t1"}
    target = {
        "id": "t1",
        "name": "demo",
        "base_url": "https://target.test",
        "credentials": {"user_a": {}, "user_b": {}},
        "passive_only": False,
    }
    _approvals_route, findings_route = _mock_common("s2", "appr2", "rejected")

    settings = _settings(tmp_path)
    api = ApiClient(settings)
    worker = ScanWorkerClient(settings)
    cooldowns = CooldownTracker(60)
    connector = FakeConnector([DiscoveredRoute(method="GET", path="/api/v1/orders/123")])

    run = ScanRun(scan, target, settings, api, worker, cooldowns, connectors=[connector])
    await run.run()

    assert findings_route.call_count == 0

    await api.aclose()
    await worker.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_access_control_bypass_flow(tmp_path):
    scan = {"id": "s3", "target_id": "t1"}
    target = {
        "id": "t1",
        "name": "demo",
        "base_url": "https://target.test",
        "credentials": {},
        "passive_only": False,
    }
    approvals_route, findings_route = _mock_common("s3", "appr3", "approved")

    # Specific (header-matched) routes must be registered before the
    # generic fallback - respx matches in registration order.
    respx.get("https://target.test/admin/panel", headers={"X-Forwarded-For": "127.0.0.1"}).mock(
        return_value=httpx.Response(200, text="ok")
    )
    respx.post("https://target.test/admin/panel", headers={"X-HTTP-Method-Override": "GET"}).mock(
        return_value=httpx.Response(200, text="ok")
    )
    respx.get("https://target.test/admin//panel").mock(return_value=httpx.Response(403, text="denied"))
    respx.get("https://target.test/admin/panel").mock(return_value=httpx.Response(403, text="denied"))

    settings = _settings(tmp_path)
    api = ApiClient(settings)
    worker = ScanWorkerClient(settings)
    cooldowns = CooldownTracker(60)
    connector = FakeConnector([DiscoveredRoute(method="GET", path="/admin/panel")])

    run = ScanRun(scan, target, settings, api, worker, cooldowns, connectors=[connector])
    await run.run()

    # baseline (admin_access approval) + 3 bypass variants (each its own
    # waf_bypass approval) = 4 approvals total.
    assert approvals_route.call_count == 4

    bodies = [_body(c.request) for c in findings_route.calls]
    assert len(bodies) == 3  # one finding per bypass variant
    confirmed = [b for b in bodies if b["status"] == "confirmed"]
    unconfirmed = [b for b in bodies if b["status"] == "unconfirmed"]
    assert len(confirmed) == 2  # origin_header_spoof + method_override succeed
    assert len(unconfirmed) == 1  # double-slash mutation still denied
    assert all(b["category"] == "broken_access_control" for b in bodies)

    await api.aclose()
    await worker.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_passive_only_target_never_contacts_worker_or_target(tmp_path):
    """The core safety guarantee behind passive_only: even with routes that
    would otherwise generate a hypothesis -> planned action, the OBSERVE
    httpx probe and every EXECUTE dispatch must be skipped - no HTTP request
    to the scan-worker or the target itself, no approval, no finding."""
    scan = {"id": "s4", "target_id": "t1"}
    target = {
        "id": "t1",
        "name": "demo",
        "base_url": "https://target.test",
        "credentials": {"user_a": {}, "user_b": {}},
        "passive_only": True,
    }
    scan_patch = respx.route(method="PATCH", url="http://api.test/scans/s4").mock(
        return_value=httpx.Response(200, json={"id": "s4", "stage": "x"})
    )
    approvals_route = respx.post("http://api.test/approvals").mock(
        return_value=httpx.Response(201, json={"id": "should-not-be-called", "status": "pending"})
    )
    findings_route = respx.post("http://api.test/findings").mock(
        return_value=httpx.Response(201, json={"id": "should-not-be-called"})
    )
    worker_httpx_route = respx.post("http://worker.test/scan/httpx").mock(
        return_value=httpx.Response(200, json={"available": True, "success": True, "results": []})
    )
    target_route = respx.route(url__regex=r"https://target\.test/.*").mock(
        return_value=httpx.Response(200, text="should never be reached")
    )

    settings = _settings(tmp_path)
    api = ApiClient(settings)
    worker = ScanWorkerClient(settings)
    cooldowns = CooldownTracker(60)
    # Same route shape that triggers a real IDOR hypothesis in the active test.
    connector = FakeConnector([DiscoveredRoute(method="GET", path="/api/v1/orders/123")])

    run = ScanRun(scan, target, settings, api, worker, cooldowns, connectors=[connector])
    await run.run()

    assert worker_httpx_route.call_count == 0
    assert target_route.call_count == 0
    assert approvals_route.call_count == 0
    assert findings_route.call_count == 0

    patch_bodies = [_body(c.request) for c in scan_patch.calls]
    done_bodies = [b for b in patch_bodies if b.get("stage") == "done"]
    assert len(done_bodies) == 1
    assert "passive_only" in done_bodies[0]["summary"]

    await api.aclose()
    await worker.aclose()
