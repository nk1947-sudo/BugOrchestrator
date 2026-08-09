from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from api.deps import AnyAuth, CurrentUser, DbSession
from api.models import Target, TargetStatus
from api.schemas import TargetCreate, TargetOut, TargetUpdate

router = APIRouter(prefix="/targets", tags=["targets"])


@router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
async def create_target(payload: TargetCreate, db: DbSession, current_user: CurrentUser) -> Target:
    """Inject a new target. `authorization_note` is required (enforced by the
    schema) so every scheduled run has a recorded scope justification - see
    docs/ARCHITECTURE.md "Scope & authorization"."""
    target = Target(
        name=payload.name,
        base_url=payload.base_url,
        authorization_note=payload.authorization_note,
        credentials=payload.credentials,
        passive_only=payload.passive_only,
        created_by=current_user.id,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


@router.get("", response_model=list[TargetOut])
async def list_targets(db: DbSession, _auth: AnyAuth) -> list[Target]:
    result = await db.execute(select(Target).order_by(Target.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{target_id}", response_model=TargetOut)
async def get_target(target_id: str, db: DbSession, _auth: AnyAuth) -> Target:
    target = await db.get(Target, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@router.patch("/{target_id}", response_model=TargetOut)
async def update_target(
    target_id: str, payload: TargetUpdate, db: DbSession, current_user: CurrentUser
) -> Target:
    target = await db.get(Target, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found")
    if payload.status is not None:
        target.status = payload.status
    if payload.passive_only is not None:
        target.passive_only = payload.passive_only
    await db.commit()
    await db.refresh(target)
    return target


def target_is_schedulable(target: Target) -> bool:
    return target.status == TargetStatus.active and bool(target.authorization_note.strip())
