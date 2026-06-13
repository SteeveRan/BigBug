"""
@file health_check.py
@description Pydantic schemas for HealthCheck API responses — severity, item, report.
@dependencies pydantic, enum
@relatedFiles ../services/health_check.py, ../api/health_check.py
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class HealthCheckSeverity(enum.StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class HealthCheckItemOut(BaseModel):
    """A single component health check result."""

    component: str
    severity: HealthCheckSeverity
    message: str
    detail: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class HealthCheckReportOut(BaseModel):
    """Full health check report for system, sync group, or mirror."""

    mirror_id: int | None = None
    sync_group_id: int | None = None
    timestamp: datetime
    overall: HealthCheckSeverity
    items: list[HealthCheckItemOut] = []

    model_config = {"from_attributes": True}
