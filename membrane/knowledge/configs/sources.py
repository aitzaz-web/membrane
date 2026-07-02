"""Source registry — tracks all knowledge sources."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from membrane.knowledge.models.provenance import SourceStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_arxiv_id(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^arxiv:", "", value, flags=re.IGNORECASE)
    match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", value)
    if match:
        return match.group(1)
    return value.replace("/", "_").replace(".", "_")


def arxiv_source_id(arxiv_id: str) -> str:
    return f"arxiv_{normalize_arxiv_id(arxiv_id).replace('.', '_')}"


def url_source_id(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", url.lower()).strip("_")
    return f"url_{slug[:80]}"


SourceType = Literal[
    "arxiv_paper",
    "http",
    "github_readme",
    "product_docs",
    "awesome_list",
    "blog",
    "benchmark",
]


class SourceEntry(BaseModel):
    id: str
    type: SourceType
    url: str
    title: str | None = None
    year: int | None = None
    category_tags: list[str] = Field(default_factory=list)
    github_url: str | None = None
    arxiv_id: str | None = None
    status: SourceStatus = "pending"
    pattern_ids: list[str] = Field(default_factory=list)
    discovered_from: str | None = None
    fetched_at: datetime | None = None
    extracted_at: datetime | None = None
    error: str | None = None

    @classmethod
    def from_arxiv_url(cls, url: str, title: str | None = None, **kwargs) -> SourceEntry:
        arxiv_id = normalize_arxiv_id(url)
        return cls(
            id=arxiv_source_id(arxiv_id),
            type="arxiv_paper",
            url=url if url.startswith("http") else f"https://arxiv.org/abs/{arxiv_id}",
            title=title,
            arxiv_id=arxiv_id,
            **kwargs,
        )


class SourceRegistry(BaseModel):
    sources: list[SourceEntry] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    def get(self, source_id: str) -> SourceEntry | None:
        return next((s for s in self.sources if s.id == source_id), None)

    def upsert(self, entry: SourceEntry) -> None:
        existing = self.get(entry.id)
        if existing:
            idx = self.sources.index(existing)
            merged = existing.model_copy(update=entry.model_dump(exclude_unset=True))
            self.sources[idx] = merged
        else:
            self.sources.append(entry)
        self.updated_at = utc_now()

    def by_status(self, status: SourceStatus) -> list[SourceEntry]:
        return [s for s in self.sources if s.status == status]

    def dedupe_key(self, entry: SourceEntry) -> str:
        if entry.arxiv_id:
            return f"arxiv:{normalize_arxiv_id(entry.arxiv_id)}"
        return entry.url.rstrip("/").lower()


DEFAULT_REGISTRY_PATH = Path(".membrane/knowledge/sources.yaml")


def load_registry(path: Path | None = None) -> SourceRegistry:
    path = path or DEFAULT_REGISTRY_PATH
    if not path.exists():
        return SourceRegistry()
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, list):
        return SourceRegistry(sources=[SourceEntry.model_validate(s) for s in data])
    return SourceRegistry.model_validate(data)


def save_registry(registry: SourceRegistry, path: Path | None = None) -> Path:
    path = path or DEFAULT_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = registry.model_dump(mode="json")
    with path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path
