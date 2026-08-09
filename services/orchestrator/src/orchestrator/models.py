from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class HypothesisCategory(str, enum.Enum):
    idor = "idor"
    broken_access_control = "broken_access_control"
    business_logic = "business_logic"
    other = "other"


class ActionCategory(str, enum.Enum):
    """Mirrors api.models.ApprovalCategory for the categories that require a
    human decision, plus `read_only_probe` for actions that never need one."""

    read_only_probe = "read_only_probe"
    admin_access = "admin_access"
    destructive_state_change = "destructive_state_change"
    aggressive_payload = "aggressive_payload"
    waf_bypass = "waf_bypass"


@dataclass
class DiscoveredRoute:
    method: str
    path: str
    sample_params: dict[str, str] = field(default_factory=dict)
    source: str = "unknown"  # e.g. "httpx", "manual"


@dataclass
class ObservedState:
    target_id: str
    base_url: str
    stack_fingerprint: dict[str, Any] = field(default_factory=dict)
    open_ports: list[dict[str, Any]] = field(default_factory=list)
    routes: list[DiscoveredRoute] = field(default_factory=list)
    credential_tiers: dict[str, dict[str, str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class Hypothesis:
    category: HypothesisCategory
    confidence: float
    description: str
    rationale: str
    route: DiscoveredRoute | None = None
    id_param: str | None = None
    id_value: str | None = None


@dataclass
class PlannedAction:
    hypothesis: Hypothesis
    category: ActionCategory
    description: str
    method: str
    path: str
    baseline_auth_tier: str | None = None
    mutated_auth_tier: str | None = None
    mutated_id_param: str | None = None
    mutated_id_value: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    confirmation_criteria: str = ""


@dataclass
class ProbeResult:
    status_code: int | None
    headers: dict[str, str]
    body: str
    duration_ms: float
    error: str | None = None
    raw_request: str = ""


@dataclass
class VerificationOutcome:
    confirmed: bool
    reason: str
    baseline: ProbeResult | None = None
    mutated: ProbeResult | None = None
