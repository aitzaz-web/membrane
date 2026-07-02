"""Knowledge unit models — flatten, tree, and chunk shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from membrane.knowledge.models.provenance import Citation, ExtractionRef, SourceRef, utc_now


class BaseKnowledge(BaseModel):
    id: str
    as_of: datetime = Field(default_factory=utc_now)
    source: SourceRef
    extraction: ExtractionRef | None = None
    tags: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    def embedding_text(self) -> str:
        raise NotImplementedError


class SectionNode(BaseModel):
    title: str
    path: str
    summary: str | None = None
    text: str | None = None
    children: list[SectionNode] = Field(default_factory=list)


class SourceDocument(BaseKnowledge):
    """Full paper or doc — section tree with content at leaves."""

    title: str
    abstract: str | None = None
    sections: list[SectionNode] = Field(default_factory=list)

    def embedding_text(self) -> str:
        parts = [self.title, self.abstract or ""]
        for section in self._flatten_sections(self.sections):
            parts.append(section)
        return "\n\n".join(p for p in parts if p)

    def _flatten_sections(self, nodes: list[SectionNode]) -> list[str]:
        texts: list[str] = []
        for node in nodes:
            if node.text:
                texts.append(f"{node.title}\n{node.text}")
            elif node.summary:
                texts.append(f"{node.title}\n{node.summary}")
            texts.extend(self._flatten_sections(node.children))
        return texts


class ArchitectureCard(BaseKnowledge):
    """Distilled pattern summary — may map to catalog/patterns/*.yaml."""

    pattern_id: str | None = None
    name: str
    one_line_summary: str
    memory_needs_served: list[str] = Field(default_factory=list)
    query_patterns_served: list[str] = Field(default_factory=list)
    reported_metrics: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    def embedding_text(self) -> str:
        return "\n".join(
            [
                self.name,
                self.one_line_summary,
                f"Needs: {', '.join(self.memory_needs_served)}",
                f"Queries: {', '.join(self.query_patterns_served)}",
                f"Strengths: {', '.join(self.strengths)}",
                f"Weaknesses: {', '.join(self.weaknesses)}",
            ]
        )


class EvidenceChunk(BaseModel):
    """Flat index row — links back to SourceDocument or ArchitectureCard."""

    id: str
    source_id: str
    chunk_type: str = "section"  # section | abstract | extraction | pattern
    section_path: str = ""
    text: str
    tags: list[str] = Field(default_factory=list)
    pattern_id: str | None = None
    citation: Citation | None = None

    def embedding_text(self) -> str:
        return self.text
