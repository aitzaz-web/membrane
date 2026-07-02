"""Provenance types for knowledge units."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceRef(BaseModel):
    source_id: str
    source_type: str
    url: str | None = None
    title: str | None = None


class Citation(BaseModel):
    page: int | None = None
    section: str | None = None
    quote: str | None = None


class ExtractionRef(BaseModel):
    extraction_id: str | None = None
    model: str | None = None
    extracted_at: datetime = Field(default_factory=utc_now)


SourceStatus = Literal["pending", "fetched", "extracted", "failed", "indexed"]
