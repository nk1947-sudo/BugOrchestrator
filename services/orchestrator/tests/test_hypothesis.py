from orchestrator.hypothesis import generate_hypotheses
from orchestrator.models import DiscoveredRoute, HypothesisCategory, ObservedState


def _observed(routes, tiers=None):
    return ObservedState(
        target_id="t1",
        base_url="https://example.test",
        routes=routes,
        credential_tiers=tiers or {},
    )


def test_no_hypotheses_without_multiple_credential_tiers():
    observed = _observed([DiscoveredRoute(method="GET", path="/api/v1/orders/123")], tiers={"user_a": {}})
    hyps = generate_hypotheses(observed)
    assert not any(h.category == HypothesisCategory.idor for h in hyps)


def test_idor_hypothesis_for_numeric_id_with_multiple_tiers():
    observed = _observed(
        [DiscoveredRoute(method="GET", path="/api/v1/orders/123")],
        tiers={"user_a": {"bearer": "a"}, "user_b": {"bearer": "b"}},
    )
    hyps = generate_hypotheses(observed)
    idor = [h for h in hyps if h.category == HypothesisCategory.idor]
    assert len(idor) == 1
    assert idor[0].id_value == "123"
    assert idor[0].id_param == "path"


def test_idor_hypothesis_for_uuid_id():
    observed = _observed(
        [DiscoveredRoute(method="GET", path="/api/v1/orders/550e8400-e29b-41d4-a716-446655440000")],
        tiers={"user_a": {}, "user_b": {}},
    )
    hyps = generate_hypotheses(observed)
    assert any(h.category == HypothesisCategory.idor for h in hyps)


def test_admin_route_always_flagged_regardless_of_tiers():
    observed = _observed([DiscoveredRoute(method="GET", path="/admin/users")], tiers={})
    hyps = generate_hypotheses(observed)
    assert any(h.category == HypothesisCategory.broken_access_control for h in hyps)


def test_tenant_param_flagged_as_business_logic():
    observed = _observed(
        [DiscoveredRoute(method="GET", path="/api/v1/billing", sample_params={"tenant_id": "42"})],
        tiers={"user_a": {}, "user_b": {}},
    )
    hyps = generate_hypotheses(observed)
    business = [h for h in hyps if h.category == HypothesisCategory.business_logic]
    assert len(business) == 1
    assert business[0].id_param == "tenant_id"
    assert business[0].id_value == "42"


def test_hypotheses_sorted_by_confidence_descending():
    observed = _observed(
        [
            DiscoveredRoute(method="GET", path="/admin/panel"),
            DiscoveredRoute(method="GET", path="/api/v1/orders/123"),
        ],
        tiers={"user_a": {}, "user_b": {}},
    )
    hyps = generate_hypotheses(observed)
    confidences = [h.confidence for h in hyps]
    assert confidences == sorted(confidences, reverse=True)


def test_ordinary_route_produces_no_hypotheses():
    observed = _observed(
        [DiscoveredRoute(method="GET", path="/api/v1/health")],
        tiers={"user_a": {}, "user_b": {}},
    )
    assert generate_hypotheses(observed) == []
