"""Load catalog taxonomy and pattern YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


CATALOG_DIR = Path(__file__).resolve().parent
PATTERNS_DIR = CATALOG_DIR / "patterns"
TAXONOMY_PATH = CATALOG_DIR / "taxonomy.yaml"


class PatternConstraints(BaseModel):
    latency_profile: str = "medium"
    cost_profile: str = "medium"
    privacy: str = "self_hostable"
    explainability: str = "medium"


class PatternEvalAffinities(BaseModel):
    benchmarks: list[str] = Field(default_factory=list)
    excels_at: list[str] = Field(default_factory=list)
    weak_at: list[str] = Field(default_factory=list)


class PatternImplementation(BaseModel):
    adapter: str
    reference_impl: str | None = None


class PatternSource(BaseModel):
    type: str
    source_id: str | None = None
    url: str | None = None
    notes: str | None = None


class ArchitecturePattern(BaseModel):
    id: str
    name: str
    version: str = "1.0"
    sources: list[PatternSource] = Field(default_factory=list)
    taxonomy: dict[str, list[str]] = Field(default_factory=dict)
    memory_needs_served: list[str] = Field(default_factory=list)
    query_patterns_served: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    infra_requirements: list[dict[str, str]] = Field(default_factory=list)
    constraints: PatternConstraints = Field(default_factory=PatternConstraints)
    eval_affinities: PatternEvalAffinities = Field(default_factory=PatternEvalAffinities)
    composable_with: list[str] = Field(default_factory=list)
    implementation: PatternImplementation | None = None
    # extraction metadata (optional, from review approvals)
    one_line_summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    reported_metrics: dict[str, float] = Field(default_factory=dict)

    def embedding_text(self) -> str:
        parts = [
            self.name,
            self.one_line_summary or "",
            f"Memory needs: {', '.join(self.memory_needs_served)}",
            f"Query patterns: {', '.join(self.query_patterns_served)}",
            f"Components: {', '.join(self.components)}",
            f"Strengths: {', '.join(self.strengths)}",
            f"Weaknesses: {', '.join(self.weaknesses)}",
        ]
        return "\n".join(p for p in parts if p)


def load_taxonomy() -> dict[str, Any]:
    with TAXONOMY_PATH.open() as f:
        return yaml.safe_load(f) or {}


def list_pattern_ids() -> list[str]:
    if not PATTERNS_DIR.exists():
        return []
    return sorted(p.stem for p in PATTERNS_DIR.glob("*.yaml"))


def load_pattern(pattern_id: str) -> ArchitecturePattern:
    path = PATTERNS_DIR / f"{pattern_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Pattern not found: {pattern_id}")
    with path.open() as f:
        data = yaml.safe_load(f)
    return ArchitecturePattern.model_validate(data)


def load_all_patterns() -> list[ArchitecturePattern]:
    return [load_pattern(pid) for pid in list_pattern_ids()]


def save_pattern(pattern: ArchitecturePattern) -> Path:
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    path = PATTERNS_DIR / f"{pattern.id}.yaml"
    data = pattern.model_dump(mode="json", exclude_none=True)
    with path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path
