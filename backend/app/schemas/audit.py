"""Audit log schemas."""

from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    username: str
    action: str
    resource_type: str
    resource_id: int | None
    resource_name: str | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogList(BaseModel):
    items: list[AuditLogOut]
    total: int
