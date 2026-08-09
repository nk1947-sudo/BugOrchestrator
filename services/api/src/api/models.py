import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class TargetStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    archived = "archived"


class ScanStage(str, enum.Enum):
    pending = "pending"
    observe = "observe"
    reason = "reason"
    plan = "plan"
    execute = "execute"
    verify = "verify"
    awaiting_approval = "awaiting_approval"
    done = "done"
    failed = "failed"


class FindingCategory(str, enum.Enum):
    idor = "idor"
    broken_access_control = "broken_access_control"
    business_logic = "business_logic"
    sqli = "sqli"
    ssrf = "ssrf"
    xss = "xss"
    other = "other"


class FindingSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class FindingStatus(str, enum.Enum):
    confirmed = "confirmed"
    unconfirmed = "unconfirmed"
    false_positive = "false_positive"


class ApprovalCategory(str, enum.Enum):
    admin_access = "admin_access"
    destructive_state_change = "destructive_state_change"
    aggressive_payload = "aggressive_payload"
    waf_bypass = "waf_bypass"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


def _enum(python_enum: type[enum.Enum], **kw):
    return Enum(python_enum, native_enum=False, validate_strings=True, **kw)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole), default=UserRole.operator)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(2048))
    # Required, non-empty: program name, ticket link, or an ownership statement.
    # Recorded for audit purposes; the platform cannot verify it independently.
    authorization_note: Mapped[str] = mapped_column(Text)
    # Optional per-tier auth material (e.g. {"user_a": {"bearer": "..."}, "user_b": {...}}).
    # In a real deployment this should be a reference into a secrets manager,
    # not raw material - flagged in docs/ARCHITECTURE.md as a follow-up.
    credentials: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[TargetStatus] = mapped_column(_enum(TargetStatus), default=TargetStatus.active)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scans: Mapped[list["Scan"]] = relationship(back_populates="target", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("targets.id"))
    stage: Mapped[ScanStage] = mapped_column(_enum(ScanStage), default=ScanStage.pending)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    target: Mapped["Target"] = relationship(back_populates="scans")
    findings: Mapped[list["Finding"]] = relationship(back_populates="scan", cascade="all, delete-orphan")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"))
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("targets.id"))
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[FindingCategory] = mapped_column(_enum(FindingCategory))
    severity: Mapped[FindingSeverity] = mapped_column(_enum(FindingSeverity))
    cvss_score: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[FindingStatus] = mapped_column(_enum(FindingStatus), default=FindingStatus.unconfirmed)
    summary: Mapped[str] = mapped_column(Text)
    evidence_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan: Mapped["Scan"] = relationship(back_populates="findings")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"))
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("targets.id"))
    category: Mapped[ApprovalCategory] = mapped_column(_enum(ApprovalCategory))
    action_description: Mapped[str] = mapped_column(Text)
    planned_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(_enum(ApprovalStatus), default=ApprovalStatus.pending)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="approvals")
