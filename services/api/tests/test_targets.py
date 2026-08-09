import pytest


@pytest.mark.asyncio
async def test_create_target_requires_authorization_note(client, auth_headers):
    resp = await client.post(
        "/targets",
        json={"name": "demo", "base_url": "https://example.test", "authorization_note": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_and_list_target(client, auth_headers):
    resp = await client.post(
        "/targets",
        json={
            "name": "demo-app",
            "base_url": "https://demo.example.test",
            "authorization_note": "HackerOne program h1-demo, enrolled 2026-08-01",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "active"
    assert body["base_url"] == "https://demo.example.test"

    listed = await client.get("/targets", headers=auth_headers)
    assert listed.status_code == 200
    assert any(t["id"] == body["id"] for t in listed.json())


@pytest.mark.asyncio
async def test_create_target_requires_auth(client):
    resp = await client.post(
        "/targets",
        json={
            "name": "demo-app",
            "base_url": "https://demo.example.test",
            "authorization_note": "owned asset",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scan_requires_active_schedulable_target(client, auth_headers):
    create = await client.post(
        "/targets",
        json={
            "name": "pausable",
            "base_url": "https://pausable.example.test",
            "authorization_note": "owned asset for testing",
        },
        headers=auth_headers,
    )
    target_id = create.json()["id"]

    paused = await client.patch(f"/targets/{target_id}", json={"status": "paused"}, headers=auth_headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    scan_attempt = await client.post(f"/targets/{target_id}/scans", headers=auth_headers)
    assert scan_attempt.status_code == 422
