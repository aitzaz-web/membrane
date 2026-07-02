"""Comparison context for agentic MAK queries."""

from __future__ import annotations

from pydantic import BaseModel, Field

from membrane.catalog.loader import ArchitecturePattern
from membrane.knowledge.models.knowledge import EvidenceChunk


class PatternComparison(BaseModel):
    pattern_id: str
    name: str
    memory_needs_served: list[str] = Field(default_factory=list)
    query_patterns_served: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    composable_with: list[str] = Field(default_factory=list)
    one_line_summary: str | None = None


class ComparisonContext(BaseModel):
    pattern_ids: list[str]
    patterns: list[PatternComparison] = Field(default_factory=list)
    evidence_chunks: list[EvidenceChunk] = Field(default_factory=list)
    comparison_query: str = ""

    @classmethod
    def from_patterns(
        cls,
        patterns: list[ArchitecturePattern],
        evidence_chunks: list[EvidenceChunk] | None = None,
        comparison_query: str = "",
    ) -> ComparisonContext:
        return cls(
            pattern_ids=[p.id for p in patterns],
            patterns=[
                PatternComparison(
                    pattern_id=p.id,
                    name=p.name,
                    memory_needs_served=p.memory_needs_served,
                    query_patterns_served=p.query_patterns_served,
                    components=p.components,
                    strengths=p.strengths,
                    weaknesses=p.weaknesses,
                    composable_with=p.composable_with,
                    one_line_summary=p.one_line_summary,
                )
                for p in patterns
            ],
            evidence_chunks=evidence_chunks or [],
            comparison_query=comparison_query,
        )
