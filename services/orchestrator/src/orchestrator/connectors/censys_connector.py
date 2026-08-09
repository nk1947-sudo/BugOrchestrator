from __future__ import annotations

import asyncio
import socket

import httpx

from orchestrator.config import Settings
from orchestrator.connectors.base import Connector, ConnectorOutcome

CENSYS_BASE_URL = "https://search.censys.io/api/v2"


class CensysConnector(Connector):
    name = "censys"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._api_id = settings.censys_api_id
        self._api_secret = settings.censys_api_secret
        self._client = client or httpx.AsyncClient(base_url=CENSYS_BASE_URL, timeout=15.0)

    @property
    def configured(self) -> bool:
        return bool(self._api_id and self._api_secret)

    async def observe(self, hostname: str) -> ConnectorOutcome:
        if not self.configured:
            return ConnectorOutcome(
                self.name, configured=False, ok=False, note="CENSYS_API_ID/CENSYS_API_SECRET not set"
            )

        try:
            ip = await asyncio.get_event_loop().run_in_executor(None, socket.gethostbyname, hostname)
        except OSError as exc:
            return ConnectorOutcome(
                self.name, configured=True, ok=False, note=f"could not resolve {hostname}: {exc}"
            )

        try:
            resp = await self._client.get(f"/hosts/{ip}", auth=(self._api_id, self._api_secret))
        except httpx.HTTPError as exc:
            return ConnectorOutcome(self.name, configured=True, ok=False, note=f"request failed: {exc}")

        if resp.status_code == 404:
            return ConnectorOutcome(self.name, configured=True, ok=True, note=f"no Censys data for {ip}")
        if resp.status_code != 200:
            return ConnectorOutcome(
                self.name, configured=True, ok=False, note=f"Censys returned HTTP {resp.status_code}"
            )

        payload = resp.json().get("result", {})
        services = payload.get("services", [])
        data = {
            "ip": ip,
            "services": [
                {"port": s.get("port"), "protocol": s.get("service_name")} for s in services
            ],
            "autonomous_system": payload.get("autonomous_system", {}).get("name"),
        }
        return ConnectorOutcome(self.name, configured=True, ok=True, note="ok", data=data)
