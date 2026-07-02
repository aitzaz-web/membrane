"""Structured extraction schema — same for all source types."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArchitectureExtraction(BaseModel):
    name: str
    one_line_summary: str
    taxonomy_tags: list[str] = Field(default_factory=list)
    memory_needs_served: list[str] = Field(default_factory=list)
    query_patterns_served: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    write_path: str = ""
    read_path: str = ""
    infra_requirements: list[str] = Field(default_factory=list)
    reported_metrics: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    comparable_to: list[str] = Field(default_factory=list)
    implementation_available: bool = False
    code_url: str | None = None
    confidence: float = 0.5
    evidence_quotes: list[str] = Field(default_factory=list)
    suggested_pattern_id: str | None = None
