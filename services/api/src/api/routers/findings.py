from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from api.deps import AnyAuth, DbSession, ServiceAuth
from api.models import Finding, FindingStatus
from api.schemas import FindingCreate, FindingOut
from api.ws import manager

router = APIRouter(prefix="/findings", tags=["findings"])


@router.post("", response_model=FindingOut, status_code=status.HTTP_201_CREATED)
async def create_finding(payload: FindingCreate, db: DbSession, _auth: ServiceAuth) -> Finding:
    """Called by the orchestrator's VERIFY stage once a hypothesis is
    confirmed or ruled out."""
    finding = Finding(**payload.model_dump())
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    if finding.status == FindingStatus.confirmed:
        await manager.broadcast(
            "finding.confirmed",
            {"id": finding.id, "title": finding.title, "severity": finding.severity.value},
        )
    return finding


@router.get("", response_model=list[FindingOut])
async def list_findings(
    db: DbSession,
    _auth: AnyAuth,
    target_id: str | None = Query(default=None),
    status_filter: FindingStatus | None = Query(default=None, alias="status"),
) -> list[Finding]:
    stmt = select(Finding).order_by(Finding.created_at.desc())
    if target_id:
        stmt = stmt.where(Finding.target_id == target_id)
    if status_filter:
        stmt = stmt.where(Finding.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{finding_id}", response_model=FindingOut)
async def get_finding(finding_id: str, db: DbSession, _auth: AnyAuth) -> Finding:
    finding = await db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding
