"""REASON stage: a rule-based hypothesis generator over OBSERVE output.

Deliberately not ML-based or fuzzy - every rule here maps to a specific,
explainable signal (a path shape, a parameter name, a credential-tier count)
so a human reviewing the approvals queue can see exactly why an action was
proposed. No hypothesis is executed by generating it; PLAN turns a subset of
these into PlannedActions, and EXECUTE still gates high-impact ones on HITL.
"""

from __future__ import annotations

import re

from orchestrator.models import Hypothesis, HypothesisCategory, ObservedState

_ID_SEGMENT_RE = re.compile(
    r"^(?:\d+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)
_ADMIN_PATH_RE = re.compile(r"/(admin|internal|management|staff|ops)(/|$)", re.IGNORECASE)
_TENANT_PARAM_RE = re.compile(r"(tenant|org|account|customer|company)[_-]?id", re.IGNORECASE)


def _find_id_segment(path: str) -> str | None:
    for segment in path.strip("/").split("/"):
        if _ID_SEGMENT_RE.match(segment):
            return segment
    return None


def generate_hypotheses(observed: ObservedState) -> list[Hypothesis]:
    hypotheses: list[Hypothesis] = []
    multi_tenant = len(observed.credential_tiers) >= 2

    for route in observed.routes:
        if _ADMIN_PATH_RE.search(route.path):
            hypotheses.append(
                Hypothesis(
                    category=HypothesisCategory.broken_access_control,
                    confidence=0.55,
                    description=f"{route.method} {route.path} matches an admin/internal route pattern",
                    rationale=(
                        "Path segment matches admin|internal|management|staff|ops - worth "
                        "checking whether a lower-privilege credential tier can reach it."
                    ),
                    route=route,
                )
            )

        id_value = _find_id_segment(route.path)
        if id_value is not None and multi_tenant:
            hypotheses.append(
                Hypothesis(
                    category=HypothesisCategory.idor,
                    confidence=0.65,
                    description=(
                        f"{route.method} {route.path} takes a raw ID in the path and "
                        "multiple credential tiers are configured"
                    ),
                    rationale=(
                        "Numeric/UUID path segment plus >=2 configured principals is the "
                        "classic IDOR setup: swap the ID under one principal's auth and see "
                        "if another principal's resource comes back."
                    ),
                    route=route,
                    id_param="path",
                    id_value=id_value,
                )
            )

        for param_name, param_value in route.sample_params.items():
            if multi_tenant and _TENANT_PARAM_RE.search(param_name):
                hypotheses.append(
                    Hypothesis(
                        category=HypothesisCategory.business_logic,
                        confidence=0.60,
                        description=(
                            f"{route.method} {route.path} accepts `{param_name}` and "
                            "multiple credential tiers are configured"
                        ),
                        rationale=(
                            f"Parameter name `{param_name}` suggests tenant/org scoping - "
                            "worth testing whether the server re-validates it against the "
                            "authenticated principal rather than trusting the client-supplied value."
                        ),
                        route=route,
                        id_param=param_name,
                        id_value=param_value,
                    )
                )

    hypotheses.sort(key=lambda h: h.confidence, reverse=True)
    return hypotheses
