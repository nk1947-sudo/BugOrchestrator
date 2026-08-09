from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ConnectorOutcome:
    connector: str
    configured: bool
    ok: bool
    note: str
    data: dict = field(default_factory=dict)


class Connector(ABC):
    name: str

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Whether this connector has the credentials it needs. Unconfigured
        connectors are skipped, not treated as errors - see OBSERVE stage."""

    @abstractmethod
    async def observe(self, hostname: str) -> ConnectorOutcome:
        ...
