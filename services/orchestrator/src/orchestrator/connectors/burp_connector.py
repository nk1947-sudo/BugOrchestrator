from __future__ import annotations

from dataclasses import dataclass

import httpx

from orchestrator.config import Settings
from orchestrator.connectors.base import Connector, ConnectorOutcome
from orchestrator.models import DiscoveredRoute


@dataclass
class RepeaterResult:
    status_code: int | None
    headers: dict[str, str]
    body: str
    error: str | None = None


class BurpConnector(Connector):
    """Wraps Burp Suite's REST API (the "REST API" extension for Burp Suite
    Professional, or an equivalent proxy exposing the same shape). Endpoint
    paths are best-effort and may need adjusting to match the exact
    extension/version in use - both methods fail closed (return a
    `configured=True, ok=False` outcome / a RepeaterResult with `.error` set)
    rather than raising, since Burp is commonly not running in every
    environment this orchestrator deploys to.
    """

    name = "burp"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = settings.burp_api_base_url
        self._api_key = settings.burp_api_key
        self._client = client or (
            httpx.AsyncClient(base_url=self._base_url, timeout=30.0) if self._base_url else None
        )

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    async def observe(self, hostname: str) -> ConnectorOutcome:
        """Pull previously captured proxy history for `hostname` - routes a
        human operator has already browsed through Burp's proxy - to seed
        OBSERVE with real traffic rather than only synthetic recon."""
        if not self.configured or self._client is None:
            return ConnectorOutcome(self.name, configured=False, ok=False, note="BURP_API_BASE_URL not set")

        try:
            resp = await self._client.get(
                "/v0.1/proxy/history", params={"host": hostname}, headers=self._headers()
            )
        except httpx.HTTPError as exc:
            return ConnectorOutcome(self.name, configured=True, ok=False, note=f"request failed: {exc}")

        if resp.status_code != 200:
            return ConnectorOutcome(
                self.name, configured=True, ok=False, note=f"Burp API returned HTTP {resp.status_code}"
            )

        entries = resp.json().get("entries", [])
        routes = [
            DiscoveredRoute(method=e.get("method", "GET"), path=e.get("path", "/"), source="burp_proxy_history")
            for e in entries
            if e.get("path")
        ]
        return ConnectorOutcome(self.name, configured=True, ok=True, note=f"{len(routes)} routes from proxy history", data={"routes": routes})

    async def send_to_repeater(self, raw_request: str, host: str, port: int, use_https: bool) -> RepeaterResult:
        if not self.configured or self._client is None:
            return RepeaterResult(status_code=None, headers={}, body="", error="BURP_API_BASE_URL not set")

        try:
            resp = await self._client.post(
                "/v0.1/repeater",
                json={"request": raw_request, "host": host, "port": port, "use_https": use_https},
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            return RepeaterResult(status_code=None, headers={}, body="", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return RepeaterResult(
                status_code=resp.status_code, headers={}, body="", error=f"Burp API returned HTTP {resp.status_code}"
            )

        payload = resp.json()
        return RepeaterResult(
            status_code=payload.get("status_code"),
            headers=payload.get("headers", {}),
            body=payload.get("body", ""),
        )
