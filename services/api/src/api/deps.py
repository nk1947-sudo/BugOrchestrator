from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.db import get_db
from api.models import User
from api.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
    except Exception as exc:  # jwt.PyJWTError and friends
        raise credentials_error from exc
    if user_id is None:
        raise credentials_error

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def verify_service_token(x_service_token: Annotated[str | None, Header()] = None) -> None:
    """Auth for machine clients (orchestrator, scan-worker) that have no user
    session - a shared secret sent as `X-Service-Token`, distinct from the
    dashboard's per-user JWTs."""
    settings = get_settings()
    if not x_service_token or x_service_token != settings.internal_service_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")


ServiceAuth = Annotated[None, Depends(verify_service_token)]


async def require_user_or_service(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_service_token: Annotated[str | None, Header()] = None,
) -> None:
    """Endpoints readable by both the dashboard (user JWT) and internal
    services (shared service token) - e.g. listing findings/approvals."""
    settings = get_settings()
    if x_service_token and x_service_token == settings.internal_service_token:
        return
    if token:
        await get_current_user(db, token)
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


AnyAuth = Annotated[None, Depends(require_user_or_service)]
