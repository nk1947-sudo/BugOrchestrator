from __future__ import annotations

from typing import Any

import httpx

from orchestrator.config import Settings


class ApiClient:
    """Thin async client for services/api's machine-facing endpoints,
    authenticated with the shared X-Service-Token (never a user JWT - the
    orchestrator is not a human operator)."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.api_internal_url,
            headers={"X-Service-Token": settings.internal_service_token},
            timeout=30.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_pending_scans(self) -> list[dict[str, Any]]:
        resp = await self._client.get("/scans/pending")
        resp.raise_for_status()
        return resp.json()

    async def get_target(self, target_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/targets/{target_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_scan(
        self,
        scan_id: str,
        *,
        stage: str | None = None,
        summary: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        body = {k: v for k, v in {"stage": stage, "summary": summary, "error": error}.items() if v is not None}
        resp = await self._client.patch(f"/scans/{scan_id}", json=body)
        resp.raise_for_status()
        return resp.json()

    async def create_finding(self, **kwargs: Any) -> dict[str, Any]:
        resp = await self._client.post("/findings", json=kwargs)
        resp.raise_for_status()
        return resp.json()

    async def create_approval(
        self,
        *,
        scan_id: str,
        target_id: str,
        category: str,
        action_description: str,
        planned_request: str | None = None,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/approvals",
            json={
                "scan_id": scan_id,
                "target_id": target_id,
                "category": category,
                "action_description": action_description,
                "planned_request": planned_request,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def get_approval(self, approval_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/approvals/{approval_id}")
        resp.raise_for_status()
        return resp.json()
