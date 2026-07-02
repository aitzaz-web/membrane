"""Raw document intermediate type between fetch and format."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class RawDocument(BaseModel):
    source_id: str
    source_type: str
    url: str
    title: str | None = None
    mime: str
    content: bytes
    metadata: dict = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"arbitrary_types_allowed": True}

    @property
    def text_hint(self) -> str | None:
        if self.mime.startswith("text/"):
            return self.content.decode("utf-8", errors="replace")
        return self.metadata.get("text")
