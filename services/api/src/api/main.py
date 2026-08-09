import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from api.config import get_settings
from api.db import async_session_factory, init_models
from api.models import User, UserRole
from api.routers import approvals, auth, findings, scans, targets
from api.security import hash_password
from api.ws import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api.main")


async def _bootstrap_admin() -> None:
    settings = get_settings()
    if not settings.admin_password:
        logger.warning("ADMIN_PASSWORD not set - skipping admin bootstrap")
        return
    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return
        admin = User(
            email=settings.admin_email,
            hashed_password=hash_password(settings.admin_password),
            role=UserRole.admin,
        )
        db.add(admin)
        await db.commit()
        logger.info("Bootstrapped initial admin user %s", settings.admin_email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    await _bootstrap_admin()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Aegis Mesh API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.dashboard_cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(targets.router)
    app.include_router(scans.router)
    app.include_router(findings.router)
    app.include_router(approvals.router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                # Dashboard clients don't send anything meaningful; this just
                # keeps the connection open and detects disconnects.
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return app


app = create_app()
