from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.models import (
    ApprovalCategory,
    ApprovalStatus,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    ScanStage,
    TargetStatus,
    UserRole,
)

# ---- auth ----


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: UserRole
    created_at: datetime


# ---- targets ----


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=2048)
    authorization_note: str = Field(
        min_length=10,
        description=(
            "Program name, ticket link, or ownership statement proving you are "
            "authorized to test this target. Required - recorded for audit, not "
            "independently verified."
        ),
    )
    credentials: dict | None = None
    passive_only: bool = Field(
        default=True,
        description=(
            "When true (default), the orchestrator never sends a request to this "
            "target - only third-party OSINT (Shodan/Censys) runs. Set to false only "
            "once you've confirmed the target's authorization explicitly permits "
            "automated scanning."
        ),
    )

    @field_validator("authorization_note")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("authorization_note cannot be blank")
        return v.strip()


class TargetUpdate(BaseModel):
    status: TargetStatus | None = None
    passive_only: bool | None = None


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str
    authorization_note: str
    passive_only: bool
    status: TargetStatus
    created_at: datetime
    updated_at: datetime


# ---- scans ----


class ScanCreate(BaseModel):
    pass


class ScanUpdate(BaseModel):
    stage: ScanStage | None = None
    summary: str | None = None
    error: str | None = None


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str
    stage: ScanStage
    summary: str | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---- findings ----


class FindingCreate(BaseModel):
    scan_id: str
    target_id: str
    title: str = Field(min_length=1, max_length=500)
    category: FindingCategory
    severity: FindingSeverity
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    status: FindingStatus = FindingStatus.unconfirmed
    summary: str
    evidence_path: str | None = None
    raw_request: str | None = None
    raw_response: str | None = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scan_id: str
    target_id: str
    title: str
    category: FindingCategory
    severity: FindingSeverity
    cvss_score: float | None
    status: FindingStatus
    summary: str
    evidence_path: str | None
    created_at: datetime


# ---- approvals ----


class ApprovalCreate(BaseModel):
    scan_id: str
    target_id: str
    category: ApprovalCategory
    action_description: str = Field(min_length=1)
    planned_request: str | None = None


class ApprovalDecision(BaseModel):
    approve: bool
    note: str | None = None


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scan_id: str
    target_id: str
    category: ApprovalCategory
    action_description: str
    planned_request: str | None
    status: ApprovalStatus
    requested_at: datetime
    decided_at: datetime | None
    decision_note: str | None
