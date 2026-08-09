"""Per-target, per-endpoint cooldown tracking.

A 429 sets a cooldown (Retry-After if the server sent one, else the
configured default) and the loop skips that endpoint until the cooldown
expires rather than retrying in place - see docs/ARCHITECTURE.md
"Rate limiting & backoff". In-memory only: a single orchestrator replica is
the deployment target for now; a multi-replica deployment would move this to
Redis (REDIS_URL is already provisioned) keyed the same way.
"""

from __future__ import annotations

import time


class CooldownTracker:
    def __init__(self, default_cooldown_seconds: int) -> None:
        self._default = default_cooldown_seconds
        self._cooldowns: dict[str, float] = {}

    @staticmethod
    def _key(target_id: str, path: str) -> str:
        return f"{target_id}:{path}"

    def is_cooling_down(self, target_id: str, path: str) -> bool:
        key = self._key(target_id, path)
        until = self._cooldowns.get(key)
        return until is not None and until > time.monotonic()

    def seconds_remaining(self, target_id: str, path: str) -> float:
        key = self._key(target_id, path)
        until = self._cooldowns.get(key)
        if until is None:
            return 0.0
        return max(0.0, until - time.monotonic())

    def set_cooldown(self, target_id: str, path: str, retry_after_seconds: float | None = None) -> None:
        seconds = retry_after_seconds if retry_after_seconds and retry_after_seconds > 0 else self._default
        self._cooldowns[self._key(target_id, path)] = time.monotonic() + seconds

    def clear(self, target_id: str, path: str) -> None:
        self._cooldowns.pop(self._key(target_id, path), None)
