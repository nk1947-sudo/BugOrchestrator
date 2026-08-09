from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import AnyAuth, CurrentUser, DbSession, ServiceAuth
from api.models import Scan, ScanStage, Target
from api.routers.targets import target_is_schedulable
from api.schemas import ScanOut, ScanUpdate
from api.ws import manager

router = APIRouter(tags=["scans"])


@router.post("/targets/{target_id}/scans", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def start_scan(target_id: str, db: DbSession, current_user: CurrentUser) -> Scan:
    target = await db.get(Target, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    if not target_is_schedulable(target):
        raise HTTPException(
            status_code=422,
            detail="Target is not schedulable (must be status=active with a non-empty authorization_note)",
        )
    scan = Scan(target_id=target.id, stage=ScanStage.pending, created_by=current_user.id)
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    await manager.broadcast("scan.created", {"id": scan.id, "target_id": target.id})
    return scan


@router.get("/scans", response_model=list[ScanOut])
async def list_scans(db: DbSession, _auth: AnyAuth) -> list[Scan]:
    result = await db.execute(select(Scan).order_by(Scan.created_at.desc()))
    return list(result.scalars().all())


@router.get("/scans/pending", response_model=list[ScanOut])
async def list_pending_scans(db: DbSession, _auth: ServiceAuth) -> list[Scan]:
    """Polled by the orchestrator to pick up new work."""
    result = await db.execute(select(Scan).where(Scan.stage == ScanStage.pending))
    return list(result.scalars().all())


@router.get("/scans/{scan_id}", response_model=ScanOut)
async def get_scan(scan_id: str, db: DbSession, _auth: AnyAuth) -> Scan:
    scan = await db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.patch("/scans/{scan_id}", response_model=ScanOut)
async def update_scan(scan_id: str, payload: ScanUpdate, db: DbSession, _auth: ServiceAuth) -> Scan:
    """Called by the orchestrator as a run advances through the loop stages."""
    scan = await db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    if payload.stage is not None:
        if scan.stage == ScanStage.pending and payload.stage != ScanStage.pending:
            scan.started_at = datetime.now(timezone.utc)
        if payload.stage in (ScanStage.done, ScanStage.failed):
            scan.finished_at = datetime.now(timezone.utc)
        scan.stage = payload.stage
    if payload.summary is not None:
        scan.summary = payload.summary
    if payload.error is not None:
        scan.error = payload.error

    await db.commit()
    await db.refresh(scan)
    await manager.broadcast("scan.updated", {"id": scan.id, "stage": scan.stage.value})
    return scan
