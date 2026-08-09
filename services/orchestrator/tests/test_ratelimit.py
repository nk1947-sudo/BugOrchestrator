from orchestrator.ratelimit import CooldownTracker


def test_not_cooling_down_by_default():
    tracker = CooldownTracker(default_cooldown_seconds=60)
    assert not tracker.is_cooling_down("t1", "/api/v1/orders")


def test_set_cooldown_uses_default_when_no_retry_after():
    tracker = CooldownTracker(default_cooldown_seconds=60)
    tracker.set_cooldown("t1", "/api/v1/orders")
    assert tracker.is_cooling_down("t1", "/api/v1/orders")
    assert tracker.seconds_remaining("t1", "/api/v1/orders") <= 60


def test_set_cooldown_prefers_retry_after():
    tracker = CooldownTracker(default_cooldown_seconds=999)
    tracker.set_cooldown("t1", "/api/v1/orders", retry_after_seconds=5)
    remaining = tracker.seconds_remaining("t1", "/api/v1/orders")
    assert remaining <= 5


def test_cooldown_is_scoped_per_target_and_path():
    tracker = CooldownTracker(default_cooldown_seconds=60)
    tracker.set_cooldown("t1", "/api/v1/orders")
    assert not tracker.is_cooling_down("t1", "/api/v1/billing")
    assert not tracker.is_cooling_down("t2", "/api/v1/orders")


def test_clear_removes_cooldown():
    tracker = CooldownTracker(default_cooldown_seconds=60)
    tracker.set_cooldown("t1", "/api/v1/orders")
    tracker.clear("t1", "/api/v1/orders")
    assert not tracker.is_cooling_down("t1", "/api/v1/orders")
