from __future__ import annotations

from typing import Any

import httpx

from orchestrator.config import Settings


class ScanWorkerClient:
    """Client for services/scan-worker (the Go microservice wrapping
    nmap/httpx/nuclei). Every method degrades gracefully: if the worker
    reports a tool unavailable, or the worker itself is unreachable, callers
    get back a dict with `available: False` rather than an exception, so a
    missing recon tool never crashes a whole scan run."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=settings.scan_worker_internal_url, timeout=120.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            resp = await self._client.get("/health")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            return {"status": "unreachable", "error": str(exc), "tools": {}}

    async def run_nmap(self, target: str, args: list[str] | None = None, timeout_seconds: int = 300) -> dict[str, Any]:
        return await self._post(
            "/scan/nmap", {"target": target, "args": args or [], "timeout_seconds": timeout_seconds}
        )

    async def run_httpx(
        self, targets: list[str], args: list[str] | None = None, timeout_seconds: int = 60
    ) -> dict[str, Any]:
        return await self._post(
            "/scan/httpx", {"targets": targets, "args": args or [], "timeout_seconds": timeout_seconds}
        )

    async def run_nuclei(
        self,
        target: str,
        templates: list[str] | None = None,
        args: list[str] | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        return await self._post(
            "/scan/nuclei",
            {
                "target": target,
                "templates": templates or [],
                "args": args or [],
                "timeout_seconds": timeout_seconds,
            },
        )

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            return {"available": False, "success": False, "error": str(exc)}
