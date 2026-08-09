from __future__ import annotations

import asyncio
import socket

import httpx

from orchestrator.config import Settings
from orchestrator.connectors.base import Connector, ConnectorOutcome

SHODAN_BASE_URL = "https://api.shodan.io"


class ShodanConnector(Connector):
    name = "shodan"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = settings.shodan_api_key
        self._client = client or httpx.AsyncClient(base_url=SHODAN_BASE_URL, timeout=15.0)

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def observe(self, hostname: str) -> ConnectorOutcome:
        if not self.configured:
            return ConnectorOutcome(self.name, configured=False, ok=False, note="SHODAN_API_KEY not set")

        try:
            ip = await asyncio.get_event_loop().run_in_executor(None, socket.gethostbyname, hostname)
        except OSError as exc:
            return ConnectorOutcome(
                self.name, configured=True, ok=False, note=f"could not resolve {hostname}: {exc}"
            )

        try:
            resp = await self._client.get(f"/shodan/host/{ip}", params={"key": self._api_key})
        except httpx.HTTPError as exc:
            return ConnectorOutcome(self.name, configured=True, ok=False, note=f"request failed: {exc}")

        if resp.status_code == 404:
            return ConnectorOutcome(self.name, configured=True, ok=True, note=f"no Shodan data for {ip}")
        if resp.status_code != 200:
            return ConnectorOutcome(
                self.name, configured=True, ok=False, note=f"Shodan returned HTTP {resp.status_code}"
            )

        payload = resp.json()
        data = {
            "ip": ip,
            "ports": payload.get("ports", []),
            "hostnames": payload.get("hostnames", []),
            "org": payload.get("org"),
            "os": payload.get("os"),
            "vulns": list(payload.get("vulns", [])),
        }
        return ConnectorOutcome(self.name, configured=True, ok=True, note="ok", data=data)
