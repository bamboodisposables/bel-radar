from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Float, String, Text
from sqlalchemy import Column
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class LookupRequest(Base):
    __tablename__ = "lookup_requests"

    id = Column(String(36), primary_key=True)
    phone_raw = Column(String(64), nullable=False)
    phone_e164 = Column(String(32), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    results = relationship("LookupResult", back_populates="request", cascade="all, delete-orphan")


class LookupResult(Base):
    __tablename__ = "lookup_results"

    id = Column(String(36), primary_key=True)
    request_id = Column(String(36), ForeignKey("lookup_requests.id", ondelete="CASCADE"), index=True)
    source = Column(String(80), nullable=False, index=True)
    match_type = Column(String(24), nullable=False, default="inconclusive")
    name = Column(String(255), nullable=True)
    account_handle = Column(String(255), nullable=True)
    account_url = Column(String(500), nullable=True)
    organization = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence = Column(JSON, nullable=False, default=list)
    details = Column(JSON, nullable=False, default=dict)
    raw = Column(JSON, nullable=False, default=dict)
    discovered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    request = relationship("LookupRequest", back_populates="results")


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(String(36), primary_key=True)
    phone_e164 = Column(String(32), nullable=False, index=True)
    source = Column(String(80), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("phone_e164", "source", name="uix_phone_source"),
    )


def expire_cache_entry(ttl_seconds: int):
    return datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)


class LookupJob(Base):
    __tablename__ = "lookup_jobs"

    id = Column(String(36), primary_key=True)
    status = Column(String(20), nullable=False, default="queued")
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    items = relationship("LookupJobItem", back_populates="job", cascade="all, delete-orphan")


class LookupJobItem(Base):
    __tablename__ = "lookup_job_items"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("lookup_jobs.id", ondelete="CASCADE"), index=True)
    phone_raw = Column(String(64), nullable=False)
    phone_e164 = Column(String(32), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="queued")
    error = Column(Text, nullable=True)
    request_id = Column(String(36), ForeignKey("lookup_requests.id"), nullable=True)
    row_index = Column(Integer, nullable=False, default=0)

    job = relationship("LookupJob", back_populates="items")
