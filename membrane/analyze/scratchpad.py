"""Shared investigation state for parallel profiling agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from membrane.knowledge.models.knowledge import EvidenceChunk


class ToolCallRecord(BaseModel):
    agent: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CodeObservation(BaseModel):
    agent: str
    kind: str  # file | dependency | infra | memory_signal
    text: str
    reference: str | None = None


class Hypothesis(BaseModel):
    text: str
    confidence: float = 0.5
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationScratchpad(BaseModel):
    """Append-only workspace shared by codebase and MAK research agents."""

    codebase_signals: list[str] = Field(default_factory=list)
    product_signals: list[str] = Field(default_factory=list)
    code_observations: list[CodeObservation] = Field(default_factory=list)
    mak_chunks: list[EvidenceChunk] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def add_signal(self, signal: str, source: Literal["codebase", "product"]) -> None:
        bucket = self.codebase_signals if source == "codebase" else self.product_signals
        if signal not in bucket:
            bucket.append(signal)

    def add_chunks(self, chunks: list[EvidenceChunk]) -> None:
        seen = {c.id for c in self.mak_chunks}
        for chunk in chunks:
            if chunk.id not in seen:
                self.mak_chunks.append(chunk)
                seen.add(chunk.id)

    def record_tool(self, agent: str, tool: str, arguments: dict, summary: str) -> None:
        self.tool_calls.append(
            ToolCallRecord(agent=agent, tool=tool, arguments=arguments, summary=summary)
        )

    def mak_source_ids(self) -> list[str]:
        return sorted({c.source_id for c in self.mak_chunks})

    def to_context_blob(self, max_chars: int = 12000) -> str:
        lines = [
            "=== Codebase signals ===",
            "\n".join(self.codebase_signals) or "(none)",
            "=== Product signals ===",
            "\n".join(self.product_signals) or "(none)",
            "=== Hypotheses ===",
        ]
        for h in self.hypotheses:
            lines.append(f"- ({h.confidence:.2f}) {h.text}")
        lines.append("=== MAK evidence (top chunks) ===")
        for chunk in self.mak_chunks[:12]:
            lines.append(f"[{chunk.source_id}/{chunk.section_path}] {chunk.text[:400]}")
        blob = "\n".join(lines)
        return blob[:max_chars]
