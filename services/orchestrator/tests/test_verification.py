from orchestrator.models import ProbeResult
from orchestrator.verification import verify_differential


def _probe(status, body="", error=None, headers=None):
    return ProbeResult(status_code=status, headers=headers or {}, body=body, duration_ms=1.0, error=error)


def test_confirmed_when_body_echoes_swapped_id():
    baseline = _probe(200, body='{"id": "A", "owner": "A"}')
    mutated = _probe(200, body='{"id": "B", "owner": "B"}')
    outcome = verify_differential(baseline, mutated, swapped_id_value="B")
    assert outcome.confirmed
    assert "swapped identifier" in outcome.reason


def test_not_confirmed_on_error():
    baseline = _probe(200, body="ok")
    mutated = _probe(None, body="", error="connection reset")
    outcome = verify_differential(baseline, mutated, swapped_id_value="B")
    assert not outcome.confirmed


def test_not_confirmed_on_denied_status():
    baseline = _probe(200, body="ok")
    mutated = _probe(403, body="forbidden")
    outcome = verify_differential(baseline, mutated, swapped_id_value="B")
    assert not outcome.confirmed


def test_not_confirmed_when_status_codes_differ():
    baseline = _probe(200, body="ok")
    mutated = _probe(201, body="ok")
    outcome = verify_differential(baseline, mutated, swapped_id_value=None)
    assert not outcome.confirmed


def test_confirmed_when_body_differs_without_explicit_id_echo():
    baseline = _probe(200, body='{"owner": "A"}')
    mutated = _probe(200, body='{"owner": "totally-different"}')
    outcome = verify_differential(baseline, mutated, swapped_id_value=None)
    assert outcome.confirmed


def test_not_confirmed_when_bodies_identical():
    baseline = _probe(200, body='{"owner": "A"}')
    mutated = _probe(200, body='{"owner": "A"}')
    outcome = verify_differential(baseline, mutated, swapped_id_value=None)
    assert not outcome.confirmed
