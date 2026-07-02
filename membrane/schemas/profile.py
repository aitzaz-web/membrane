"""AgentProfile draft — output of agentic profiling (full schema expands later)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileDraft(BaseModel):
    """Minimal profile for orchestrator v1; grows into full AgentProfile."""

    product_type: str = "unknown"
    memory_needs: list[str] = Field(default_factory=list)
    query_patterns: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    mak_evidence_ids: list[str] = Field(default_factory=list)
    tool_call_count: int = 0
    confidence: float = 0.5
    rationale: str = ""

    def to_search_query(self) -> str:
        return " ".join(
            [
                self.product_type,
                f"memory_needs:{','.join(self.memory_needs)}",
                f"query_patterns:{','.join(self.query_patterns)}",
            ]
        )
