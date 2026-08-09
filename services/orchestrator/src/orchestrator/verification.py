"""VERIFY stage: turns a (baseline, mutated) probe pair into a confirmed /
not-confirmed decision. Deliberately conservative - an inconclusive result
(different status codes, an error, no body diff) is reported as
`unconfirmed`, never guessed as confirmed."""

from __future__ import annotations

from orchestrator.models import ProbeResult, VerificationOutcome


def verify_differential(
    baseline: ProbeResult, mutated: ProbeResult, swapped_id_value: str | None
) -> VerificationOutcome:
    if mutated.error:
        return VerificationOutcome(
            confirmed=False, reason=f"mutated request errored: {mutated.error}", baseline=baseline, mutated=mutated
        )

    if mutated.status_code is None or mutated.status_code >= 400:
        return VerificationOutcome(
            confirmed=False,
            reason=f"mutated request returned {mutated.status_code}, not a success status",
            baseline=baseline,
            mutated=mutated,
        )

    if baseline.status_code != mutated.status_code:
        return VerificationOutcome(
            confirmed=False,
            reason=f"status differs from baseline ({baseline.status_code} vs {mutated.status_code}); inconclusive",
            baseline=baseline,
            mutated=mutated,
        )

    if swapped_id_value and swapped_id_value in mutated.body:
        return VerificationOutcome(
            confirmed=True,
            reason=(
                f"response body echoes the swapped identifier {swapped_id_value!r} while "
                "authenticated as a different principal"
            ),
            baseline=baseline,
            mutated=mutated,
        )

    if baseline.body and mutated.body and baseline.body != mutated.body:
        return VerificationOutcome(
            confirmed=True,
            reason="response body differs from the authenticated principal's own baseline despite an identical success status",
            baseline=baseline,
            mutated=mutated,
        )

    return VerificationOutcome(
        confirmed=False, reason="no differential signal found", baseline=baseline, mutated=mutated
    )
