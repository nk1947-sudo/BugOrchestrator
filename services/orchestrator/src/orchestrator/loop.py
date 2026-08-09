"""The OBSERVE -> REASON -> PLAN -> EXECUTE -> VERIFY state machine.

ScanRun.run() is the whole loop for one Target. Every stage transition is
reported to services/api via ApiClient.update_scan so the dashboard reflects
live progress, and every action whose category is in
settings.hitl_categories blocks on a human decision (ApiClient.create_approval
+ polling ApiClient.get_approval) before EXECUTE actually dispatches it -
see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from orchestrator.api_client import ApiClient
from orchestrator.bypass import BypassVariant, build_bypass_variants
from orchestrator.config import Settings
from orchestrator.connectors.base import Connector
from orchestrator.connectors.burp_connector import BurpConnector
from orchestrator.connectors.censys_connector import CensysConnector
from orchestrator.connectors.shodan_connector import ShodanConnector
from orchestrator.hypothesis import generate_hypotheses
from orchestrator.models import (
    ActionCategory,
    Hypothesis,
    HypothesisCategory,
    ObservedState,
    PlannedAction,
    ProbeResult,
    VerificationOutcome,
)
from orchestrator.ratelimit import CooldownTracker
from orchestrator.reporting import write_finding_report
from orchestrator.scan_worker_client import ScanWorkerClient
from orchestrator.target_client import TargetClient
from orchestrator.verification import verify_differential

logger = logging.getLogger("orchestrator.loop")

# "Zero noise" cap - a handful of well-reasoned probes per run, not an
# open-ended fuzzing pass. See hypothesis.py for how candidates are ranked.
MAX_ACTIONS_PER_RUN = 8
MAX_BYPASS_VARIANTS_PER_ROUTE = 3

_APPROVAL_POLL_SECONDS = 5


def category_for_hypothesis(h: Hypothesis, method: str) -> ActionCategory:
    if h.category == HypothesisCategory.broken_access_control:
        return ActionCategory.admin_access
    if method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
        return ActionCategory.destructive_state_change
    return ActionCategory.aggressive_payload


def plan_actions(hypotheses: list[Hypothesis]) -> list[PlannedAction]:
    """PLAN stage as a pure function - easy to unit test without any I/O."""
    planned: list[PlannedAction] = []
    for h in hypotheses[:MAX_ACTIONS_PER_RUN]:
        if h.route is None:
            continue
        method = h.route.method
        planned.append(
            PlannedAction(
                hypothesis=h,
                category=category_for_hypothesis(h, method),
                description=h.description,
                method=method,
                path=h.route.path,
                mutated_id_param=h.id_param,
                mutated_id_value=h.id_value,
                confirmation_criteria=(
                    "mutated response returns a success status matching the baseline and "
                    "either echoes the swapped identifier or differs from the baseline body"
                ),
            )
        )
    return planned


class ScanRun:
    def __init__(
        self,
        scan: dict[str, Any],
        target: dict[str, Any],
        settings: Settings,
        api: ApiClient,
        worker: ScanWorkerClient,
        cooldowns: CooldownTracker,
        connectors: list[Connector] | None = None,
        target_client: TargetClient | None = None,
    ) -> None:
        self.scan_id: str = scan["id"]
        self.target = target
        self.settings = settings
        self.api = api
        self.worker = worker
        self.cooldowns = cooldowns
        self.connectors = connectors if connectors is not None else [
            ShodanConnector(settings),
            CensysConnector(settings),
            BurpConnector(settings),
        ]
        self._target_client = target_client
        self._owns_target_client = target_client is None

    def _hostname(self) -> str:
        return urlparse(self.target["base_url"]).hostname or self.target["base_url"]

    async def run(self) -> None:
        try:
            observed = await self._observe()
            hypotheses = await self._reason(observed)
            actions = await self._plan(hypotheses)
            await self._execute_and_verify(actions)
            if self.target.get("passive_only", True):
                summary = (
                    f"passive_only target - {len(actions)} action(s) planned but none dispatched "
                    "(no request sent to the target)"
                )
            else:
                summary = f"{len(actions)} action(s) evaluated"
            await self.api.update_scan(self.scan_id, stage="done", summary=summary)
        except Exception as exc:  # noqa: BLE001 - top-level run boundary; failure must not crash the poller
            logger.exception("scan %s failed", self.scan_id)
            await self.api.update_scan(self.scan_id, stage="failed", error=str(exc))
        finally:
            if self._owns_target_client and self._target_client is not None:
                await self._target_client.aclose()

    # ---- OBSERVE ----

    async def _observe(self) -> ObservedState:
        await self.api.update_scan(self.scan_id, stage="observe")
        hostname = self._hostname()
        observed = ObservedState(
            target_id=self.target["id"],
            base_url=self.target["base_url"],
            credential_tiers=(self.target.get("credentials") or {}),
        )

        for connector in self.connectors:
            outcome = await connector.observe(hostname)
            if not outcome.configured:
                observed.notes.append(f"{connector.name}: skipped ({outcome.note})")
                continue
            if not outcome.ok:
                observed.notes.append(f"{connector.name}: {outcome.note}")
                continue
            observed.stack_fingerprint[connector.name] = {
                k: v for k, v in outcome.data.items() if k != "routes"
            }
            observed.routes.extend(outcome.data.get("routes", []))

        if self.target.get("passive_only", True):
            observed.notes.append(
                "target is passive_only - skipped scan-worker httpx probe (no request sent to the target)"
            )
        else:
            httpx_result = await self.worker.run_httpx([self.target["base_url"]])
            if httpx_result.get("available"):
                for r in httpx_result.get("results", []):
                    observed.stack_fingerprint["httpx"] = {
                        "webserver": r.get("webserver"),
                        "tech": r.get("tech"),
                        "title": r.get("title"),
                    }
            else:
                observed.notes.append(f"scan-worker httpx: unavailable ({httpx_result.get('error', 'n/a')})")

        return observed

    # ---- REASON / PLAN ----

    async def _reason(self, observed: ObservedState) -> list[Hypothesis]:
        await self.api.update_scan(self.scan_id, stage="reason")
        return generate_hypotheses(observed)

    async def _plan(self, hypotheses: list[Hypothesis]) -> list[PlannedAction]:
        await self.api.update_scan(self.scan_id, stage="plan")
        return plan_actions(hypotheses)

    # ---- EXECUTE / VERIFY ----

    async def _execute_and_verify(self, actions: list[PlannedAction]) -> None:
        if not actions:
            return
        if self.target.get("passive_only", True):
            logger.info(
                "target %s is passive_only - skipping EXECUTE for %d planned action(s)",
                self.target["id"],
                len(actions),
            )
            return
        await self.api.update_scan(self.scan_id, stage="execute")

        client = self._target_client or TargetClient(self.target["base_url"])
        self._target_client = client

        for action in actions:
            if self.cooldowns.is_cooling_down(self.target["id"], action.path):
                logger.info(
                    "skipping %s %s: cooling down for %.0fs",
                    action.method,
                    action.path,
                    self.cooldowns.seconds_remaining(self.target["id"], action.path),
                )
                continue

            if action.hypothesis.category == HypothesisCategory.broken_access_control:
                await self._run_access_control_check(client, action)
            else:
                await self._run_differential_check(client, action)

    async def _run_differential_check(self, client: TargetClient, action: PlannedAction) -> None:
        if action.category.value in self.settings.hitl_categories:
            approved = await self._await_approval(action.category, action.description, f"{action.method} {action.path}")
            if not approved:
                return

        baseline = await client.probe(action.method, action.path)
        if self._maybe_cooldown(action.path, baseline):
            return

        if action.mutated_id_param != "path" or not action.mutated_id_value:
            # We only have a safe, generic way to mutate identifiers embedded
            # directly in the path. Parameter-embedded identifiers (e.g. a
            # tenant_id in a query string or JSON body) need a route-specific
            # mutation this platform doesn't have enough context to build
            # safely - record the baseline for manual follow-up instead of
            # guessing at a request shape.
            await self.api.create_finding(
                scan_id=self.scan_id,
                target_id=self.target["id"],
                title=action.description,
                category=action.hypothesis.category.value,
                severity="info",
                status="unconfirmed",
                summary=(
                    f"Flagged for manual review: `{action.mutated_id_param}` is not a "
                    "path-embedded identifier, so no automatic differential mutation was attempted."
                ),
                raw_request=baseline.raw_request,
                raw_response=f"HTTP {baseline.status_code}",
            )
            return

        swapped_value = action.mutated_id_value + "1"
        mutated_path = action.path.replace(action.mutated_id_value, swapped_value)
        mutated = await client.probe(action.method, mutated_path, headers=action.extra_headers)
        if self._maybe_cooldown(action.path, mutated):
            return

        await self.api.update_scan(self.scan_id, stage="verify")
        outcome = verify_differential(baseline, mutated, swapped_value)
        await self._report_differential(action, swapped_value, baseline, mutated, outcome)

    async def _run_access_control_check(self, client: TargetClient, action: PlannedAction) -> None:
        if action.category.value in self.settings.hitl_categories:
            approved = await self._await_approval(action.category, action.description, f"{action.method} {action.path}")
            if not approved:
                return

        baseline = await client.probe(action.method, action.path)
        if self._maybe_cooldown(action.path, baseline):
            return

        if baseline.status_code != 403:
            await self.api.create_finding(
                scan_id=self.scan_id,
                target_id=self.target["id"],
                title=action.description,
                category=action.hypothesis.category.value,
                severity="info",
                status="unconfirmed",
                summary=(
                    f"Baseline request returned {baseline.status_code}, not 403 - no access "
                    "restriction observed to test a bypass against."
                ),
                raw_request=baseline.raw_request,
                raw_response=f"HTTP {baseline.status_code}",
            )
            return

        for variant in build_bypass_variants(action.method, action.path)[:MAX_BYPASS_VARIANTS_PER_ROUTE]:
            approved = await self._await_approval(
                ActionCategory.waf_bypass,
                f"Access-control bypass ({variant.technique}) on {action.path}: {variant.description}",
                f"{variant.method} {variant.path}",
            )
            if not approved:
                continue

            mutated = await client.probe(variant.method, variant.path, headers=variant.extra_headers)
            if self._maybe_cooldown(action.path, mutated):
                continue

            confirmed = mutated.status_code is not None and mutated.status_code < 400
            reason = (
                f"bypass technique {variant.technique!r} returned {mutated.status_code} after a 403 baseline"
                if confirmed
                else f"bypass technique {variant.technique!r} still returned {mutated.status_code}; access control held"
            )
            await self._report_bypass(action, variant, baseline, mutated, confirmed, reason)

    def _maybe_cooldown(self, path: str, probe: ProbeResult) -> bool:
        if probe.status_code == 429:
            retry_after = probe.headers.get("retry-after")
            self.cooldowns.set_cooldown(
                self.target["id"],
                path,
                float(retry_after) if retry_after and retry_after.isdigit() else None,
            )
            return True
        return False

    async def _await_approval(self, category: ActionCategory, description: str, planned_request: str) -> bool:
        approval = await self.api.create_approval(
            scan_id=self.scan_id,
            target_id=self.target["id"],
            category=category.value,
            action_description=description,
            planned_request=planned_request,
        )
        await self.api.update_scan(self.scan_id, stage="awaiting_approval")

        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.settings.hitl_approval_timeout_seconds
        while loop.time() < deadline:
            current = await self.api.get_approval(approval["id"])
            if current["status"] == "approved":
                await self.api.update_scan(self.scan_id, stage="execute")
                return True
            if current["status"] in ("rejected", "expired"):
                await self.api.update_scan(self.scan_id, stage="execute")
                return False
            await asyncio.sleep(_APPROVAL_POLL_SECONDS)

        return False

    async def _report_differential(
        self,
        action: PlannedAction,
        swapped_value: str,
        baseline: ProbeResult,
        mutated: ProbeResult,
        outcome: VerificationOutcome,
    ) -> None:
        severity = "high" if action.hypothesis.category == HypothesisCategory.idor else "medium"
        status = "confirmed" if outcome.confirmed else "unconfirmed"
        evidence_path = None

        if outcome.confirmed:
            evidence_path = write_finding_report(
                self.settings.findings_dir,
                target_name=self.target["name"],
                category=action.hypothesis.category.value,
                severity=severity,
                title=action.description,
                summary=outcome.reason,
                steps=[
                    "Authenticate as the baseline principal.",
                    f"Send the original request: {action.method} {action.path}",
                    f"Send the mutated request under the same auth, swapping the identifier to {swapped_value!r}.",
                    "Observe the mutated response returns another principal's data despite an identical success status.",
                ],
                raw_baseline_request=baseline.raw_request,
                raw_baseline_response=f"HTTP {baseline.status_code}\n\n{baseline.body[:2000]}",
                raw_mutated_request=mutated.raw_request,
                raw_mutated_response=f"HTTP {mutated.status_code}\n\n{mutated.body[:2000]}",
                remediation=(
                    "Re-validate object/tenant ownership server-side for the authenticated "
                    "principal on every request; never trust a client-supplied identifier alone."
                ),
            )

        await self.api.create_finding(
            scan_id=self.scan_id,
            target_id=self.target["id"],
            title=action.description,
            category=action.hypothesis.category.value,
            severity=severity,
            status=status,
            summary=outcome.reason,
            evidence_path=evidence_path,
            raw_request=mutated.raw_request,
            raw_response=mutated.body[:5000],
        )

    async def _report_bypass(
        self,
        action: PlannedAction,
        variant: BypassVariant,
        baseline: ProbeResult,
        mutated: ProbeResult,
        confirmed: bool,
        reason: str,
    ) -> None:
        status = "confirmed" if confirmed else "unconfirmed"
        title = f"Access-control bypass via {variant.technique} on {action.path}"
        evidence_path = None

        if confirmed:
            evidence_path = write_finding_report(
                self.settings.findings_dir,
                target_name=self.target["name"],
                category="broken_access_control",
                severity="high",
                title=title,
                summary=reason,
                steps=[
                    f"Send the baseline request: {action.method} {action.path} -> {baseline.status_code}",
                    f"Apply the {variant.technique} bypass: {variant.description}",
                    f"Resend as: {variant.method} {variant.path} with headers {variant.extra_headers}",
                    "Observe the bypassed request succeeds despite the baseline being denied.",
                ],
                raw_baseline_request=baseline.raw_request,
                raw_baseline_response=f"HTTP {baseline.status_code}",
                raw_mutated_request=mutated.raw_request,
                raw_mutated_response=f"HTTP {mutated.status_code}\n\n{mutated.body[:2000]}",
                remediation=(
                    "Enforce access control in the origin application, not only at a proxy/WAF "
                    "layer; treat X-Forwarded-For/X-HTTP-Method-Override and similar headers as "
                    "untrusted client input."
                ),
            )

        await self.api.create_finding(
            scan_id=self.scan_id,
            target_id=self.target["id"],
            title=title,
            category="broken_access_control",
            severity="high" if confirmed else "info",
            status=status,
            summary=reason,
            evidence_path=evidence_path,
            raw_request=mutated.raw_request,
            raw_response=mutated.body[:5000],
        )
