"""Entrypoint: polls services/api for pending scans and runs each through
ScanRun, bounded by ORCHESTRATOR_MAX_CONCURRENT_TARGETS concurrent runs."""

from __future__ import annotations

import asyncio
import logging

from orchestrator.api_client import ApiClient
from orchestrator.config import get_settings
from orchestrator.loop import ScanRun
from orchestrator.ratelimit import CooldownTracker
from orchestrator.scan_worker_client import ScanWorkerClient

logger = logging.getLogger("orchestrator.main")


async def _run_scan(scan: dict, api: ApiClient, worker: ScanWorkerClient, cooldowns: CooldownTracker, sem: asyncio.Semaphore) -> None:
    async with sem:
        try:
            target = await api.get_target(scan["target_id"])
        except Exception:  # noqa: BLE001
            logger.exception("failed to fetch target %s for scan %s", scan["target_id"], scan["id"])
            return
        run = ScanRun(scan, target, get_settings(), api, worker, cooldowns)
        await run.run()


async def poll_forever() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    api = ApiClient(settings)
    worker = ScanWorkerClient(settings)
    cooldowns = CooldownTracker(settings.rate_limit_default_cooldown_seconds)
    sem = asyncio.Semaphore(settings.max_concurrent_targets)

    logger.info("orchestrator polling %s every %ss", settings.api_internal_url, settings.poll_interval_seconds)

    try:
        while True:
            try:
                pending = await api.list_pending_scans()
            except Exception:  # noqa: BLE001
                logger.exception("failed to list pending scans; retrying next cycle")
                pending = []

            if pending:
                logger.info("picked up %d pending scan(s)", len(pending))
                await asyncio.gather(*(_run_scan(s, api, worker, cooldowns, sem) for s in pending))

            await asyncio.sleep(settings.poll_interval_seconds)
    finally:
        await api.aclose()
        await worker.aclose()


def main() -> None:
    asyncio.run(poll_forever())


if __name__ == "__main__":
    main()
