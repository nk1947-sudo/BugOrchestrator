from __future__ import annotations

import time

import httpx

from orchestrator.models import ProbeResult


class TargetClient:
    """Sends the orchestrator's own differential probes directly to a
    target's base_url - distinct from ScanWorkerClient, which only talks to
    the Go recon microservice. Every probe here comes from a PlannedAction
    that is either a single read-only request or something already approved
    through the HITL gate; this client does not decide what to send, only
    sends it and captures the result."""

    def __init__(
        self, base_url: str, timeout_seconds: float = 15.0, client: httpx.AsyncClient | None = None
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, follow_redirects=False
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def probe(self, method: str, path: str, headers: dict[str, str] | None = None) -> ProbeResult:
        headers = headers or {}
        raw_request = f"{method} {path} HTTP/1.1\n" + "\n".join(f"{k}: {v}" for k, v in headers.items())
        start = time.monotonic()
        try:
            resp = await self._client.request(method, path, headers=headers)
        except httpx.HTTPError as exc:
            return ProbeResult(
                status_code=None,
                headers={},
                body="",
                duration_ms=(time.monotonic() - start) * 1000,
                error=str(exc),
                raw_request=raw_request,
            )
        return ProbeResult(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            body=resp.text[:20000],
            duration_ms=(time.monotonic() - start) * 1000,
            raw_request=raw_request,
        )
