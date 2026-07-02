"""Hybrid architecture composition — stacks built from catalog patterns."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


class HybridComponent(BaseModel):
    """One catalog pattern playing a role in a composed stack."""

    role: str
    pattern_id: str
    serves: list[str] = Field(default_factory=list)
    write_path: str | None = None
    read_path: str | None = None
    scope: str | None = None
    notes: str | None = None


class RouterRule(BaseModel):
    when: list[str] = Field(default_factory=list)
    use_role: str
    description: str | None = None


class RouterSpec(BaseModel):
    type: Literal["intent_routing", "query_pattern_routing", "single_default"] = "query_pattern_routing"
    rules: list[RouterRule] = Field(default_factory=list)
    default_role: str | None = None


class HybridArchitecture(BaseModel):
    """A memory stack composed from multiple catalog patterns."""

    id: str
    name: str
    type: Literal["hybrid"] = "hybrid"
    base_patterns: list[str] = Field(default_factory=list)
    components: list[HybridComponent] = Field(default_factory=list)
    router: RouterSpec = Field(default_factory=RouterSpec)
    rationale: str | None = None
    evidence_source_ids: list[str] = Field(default_factory=list)

    def pattern_ids(self) -> list[str]:
        return list({c.pattern_id for c in self.components})


class MonolithicCandidate(BaseModel):
    """A single catalog pattern as an eval candidate."""

    id: str
    name: str
    type: Literal["monolithic"] = "monolithic"
    pattern_id: str
    rationale: str | None = None


ArchitectureCandidate = HybridArchitecture | MonolithicCandidate


def slug_hybrid_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:60]
