from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LookupRequestInput(BaseModel):
    phone_number: str = Field(..., min_length=3, examples=["06 12 34 56 78"])
    force_refresh: bool = False


class LookupResultOut(BaseModel):
    source: str
    platform: str | None = None
    match_type: str
    name: Optional[str] = None
    account_handle: Optional[str] = None
    account_url: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime

    class Config:
        from_attributes = True


class LookupResponse(BaseModel):
    request_id: str
    phone_raw: str
    phone_e164: str
    status: str
    cached: bool = False
    results: list[LookupResultOut]


class BulkLookupRequest(BaseModel):
    numbers: list[str]
    force_refresh: bool = False
    async_mode: bool = True
    max_items: int = 100


class BulkLookupSyncResponse(BaseModel):
    status: str = "completed"
    request_count: int
    results: list[LookupResponse]


class BulkLookupJobResponse(BaseModel):
    status: str = "queued"
    job_id: str
    total_items: int
    async_mode: bool = True


class JobItemOut(BaseModel):
    request_id: Optional[str]
    phone_raw: str
    phone_e164: Optional[str]
    status: str
    error: Optional[str] = None
    row_index: int


class JobStatusOut(BaseModel):
    job_id: str
    status: str
    total_items: int
    processed_items: int
    percent: float
    items: list[JobItemOut]
    error: Optional[str] = None
