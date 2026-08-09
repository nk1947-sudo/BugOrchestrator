import pytest


async def _create_target_and_scan(client, auth_headers):
    target_resp = await client.post(
        "/targets",
        json={
            "name": "hitl-target",
            "base_url": "https://hitl.example.test",
            "authorization_note": "owned asset for testing",
        },
        headers=auth_headers,
    )
    target = target_resp.json()
    scan_resp = await client.post(f"/targets/{target['id']}/scans", headers=auth_headers)
    return target, scan_resp.json()


@pytest.mark.asyncio
async def test_service_token_can_create_approval_but_not_decide(client, auth_headers, service_headers):
    target, scan = await _create_target_and_scan(client, auth_headers)

    created = await client.post(
        "/approvals",
        json={
            "scan_id": scan["id"],
            "target_id": target["id"],
            "category": "waf_bypass",
            "action_description": "Test X-Forwarded-For origin bypass on /admin",
            "planned_request": "GET /admin HTTP/1.1\nX-Forwarded-For: 127.0.0.1",
        },
        headers=service_headers,
    )
    assert created.status_code == 201, created.text
    approval = created.json()
    assert approval["status"] == "pending"

    # A service token is not a user session - it cannot approve/reject.
    denied = await client.post(
        f"/approvals/{approval['id']}/decision",
        json={"approve": True},
        headers=service_headers,
    )
    assert denied.status_code == 401


@pytest.mark.asyncio
async def test_human_approves_pending_action(client, auth_headers, service_headers):
    target, scan = await _create_target_and_scan(client, auth_headers)

    created = await client.post(
        "/approvals",
        json={
            "scan_id": scan["id"],
            "target_id": target["id"],
            "category": "aggressive_payload",
            "action_description": "Differential IDOR probe swapping tenant_id",
        },
        headers=service_headers,
    )
    approval_id = created.json()["id"]

    decided = await client.post(
        f"/approvals/{approval_id}/decision",
        json={"approve": True, "note": "Looks safe, single read-only probe"},
        headers=auth_headers,
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"

    # Approving twice is rejected - the gate is a one-shot decision.
    redecide = await client.post(
        f"/approvals/{approval_id}/decision",
        json={"approve": False},
        headers=auth_headers,
    )
    assert redecide.status_code == 409


@pytest.mark.asyncio
async def test_confirmed_finding_reported_by_service(client, auth_headers, service_headers):
    target, scan = await _create_target_and_scan(client, auth_headers)

    created = await client.post(
        "/findings",
        json={
            "scan_id": scan["id"],
            "target_id": target["id"],
            "title": "IDOR on /api/v1/billing via tenant_id",
            "category": "idor",
            "severity": "high",
            "cvss_score": 8.1,
            "status": "confirmed",
            "summary": "Swapping tenant_id under User A's JWT returned User B's invoices.",
        },
        headers=service_headers,
    )
    assert created.status_code == 201, created.text

    listed = await client.get(f"/findings?target_id={target['id']}&status=confirmed", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
