from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from api.deps import AnyAuth, CurrentUser, DbSession, ServiceAuth
from api.models import Approval, ApprovalStatus
from api.schemas import ApprovalCreate, ApprovalDecision, ApprovalOut
from api.ws import manager

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("", response_model=ApprovalOut, status_code=status.HTTP_201_CREATED)
async def create_approval(payload: ApprovalCreate, db: DbSession, _auth: ServiceAuth) -> Approval:
    """Called by the orchestrator's EXECUTE stage before running any action
    whose category is in HITL_REQUIRED_CATEGORIES. The orchestrator then
    polls GET /approvals/{id} until status leaves `pending`."""
    approval = Approval(**payload.model_dump())
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    await manager.broadcast(
        "approval.created",
        {"id": approval.id, "category": approval.category.value, "target_id": approval.target_id},
    )
    return approval


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    db: DbSession,
    _auth: AnyAuth,
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
) -> list[Approval]:
    stmt = select(Approval).order_by(Approval.requested_at.desc())
    if status_filter:
        stmt = stmt.where(Approval.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(approval_id: str, db: DbSession, _auth: AnyAuth) -> Approval:
    approval = await db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/{approval_id}/decision", response_model=ApprovalOut)
async def decide_approval(
    approval_id: str, payload: ApprovalDecision, db: DbSession, current_user: CurrentUser
) -> Approval:
    """Human decision from the dashboard. Only a logged-in user (never the
    service token) can approve or reject - this is the actual HITL gate."""
    approval = await db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != ApprovalStatus.pending:
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status.value}")

    approval.status = ApprovalStatus.approved if payload.approve else ApprovalStatus.rejected
    approval.decided_at = datetime.now(timezone.utc)
    approval.decided_by = current_user.id
    approval.decision_note = payload.note

    await db.commit()
    await db.refresh(approval)
    await manager.broadcast(
        "approval.decided", {"id": approval.id, "status": approval.status.value}
    )
    return approval
