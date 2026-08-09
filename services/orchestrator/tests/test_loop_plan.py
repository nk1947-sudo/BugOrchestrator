from orchestrator.loop import MAX_ACTIONS_PER_RUN, category_for_hypothesis, plan_actions
from orchestrator.models import ActionCategory, DiscoveredRoute, Hypothesis, HypothesisCategory


def _hyp(category, method="GET", path="/api/v1/orders/123", id_param=None, id_value=None):
    return Hypothesis(
        category=category,
        confidence=0.6,
        description="d",
        rationale="r",
        route=DiscoveredRoute(method=method, path=path),
        id_param=id_param,
        id_value=id_value,
    )


def test_admin_hypothesis_maps_to_admin_access_category():
    assert category_for_hypothesis(_hyp(HypothesisCategory.broken_access_control), "GET") == ActionCategory.admin_access


def test_get_idor_hypothesis_maps_to_aggressive_payload():
    assert category_for_hypothesis(_hyp(HypothesisCategory.idor), "GET") == ActionCategory.aggressive_payload


def test_mutating_method_maps_to_destructive_state_change():
    assert category_for_hypothesis(_hyp(HypothesisCategory.idor), "DELETE") == ActionCategory.destructive_state_change


def test_plan_actions_skips_hypotheses_without_a_route():
    h = Hypothesis(category=HypothesisCategory.other, confidence=0.5, description="d", rationale="r", route=None)
    assert plan_actions([h]) == []


def test_plan_actions_caps_at_max_actions_per_run():
    hyps = [_hyp(HypothesisCategory.idor, path=f"/api/v1/orders/{i}", id_value=str(i)) for i in range(50)]
    planned = plan_actions(hyps)
    assert len(planned) == MAX_ACTIONS_PER_RUN


def test_plan_actions_carries_id_param_and_value_through():
    h = _hyp(HypothesisCategory.idor, id_param="path", id_value="123")
    planned = plan_actions([h])
    assert planned[0].mutated_id_param == "path"
    assert planned[0].mutated_id_value == "123"
