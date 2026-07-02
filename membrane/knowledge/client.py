"""MAKClient — query interface for the knowledge base."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from membrane.catalog.loader import ArchitecturePattern, load_all_patterns, load_pattern, load_taxonomy
from membrane.knowledge.configs.sources import load_registry
from membrane.knowledge.comparison import ComparisonContext
from membrane.knowledge.index.store import SearchResult, VectorIndex
from membrane.knowledge.models.knowledge import EvidenceChunk, SourceDocument
from membrane.knowledge.storage.layout import KnowledgeLayout


@dataclass
class MAKStats:
    pattern_count: int
    source_count: int
    sources_pending: int
    sources_fetched: int
    sources_extracted: int
    sources_failed: int
    document_count: int
    indexed_chunks: int
    pending_reviews: int
    taxonomy_axes: int


@dataclass
class MAKContext:
    """Stub for Part A — profile-aware retrieval (K7)."""

    chunks: list[EvidenceChunk]
    patterns: list[ArchitecturePattern]


class MAKClient:
    def __init__(
        self,
        layout: KnowledgeLayout | None = None,
        index: VectorIndex | None = None,
    ) -> None:
        self.layout = layout or KnowledgeLayout()
        self.index = index or VectorIndex(layout=self.layout)

    def search(self, query: str, tags: list[str] | None = None, limit: int = 10) -> list[SearchResult]:
        return self.index.search(query, limit=limit, tags=tags)

    def get_pattern(self, pattern_id: str) -> ArchitecturePattern:
        return load_pattern(pattern_id)

    def get_source(self, source_id: str) -> SourceDocument | None:
        return self.layout.load_document(source_id)

    def compare(
        self,
        pattern_ids: list[str],
        focus: str | None = None,
        evidence_limit: int = 6,
    ) -> ComparisonContext:
        """Side-by-side pattern fields plus MAK evidence for agentic composition."""
        patterns = [load_pattern(pid) for pid in pattern_ids]
        query = focus or " vs ".join(pattern_ids) + " memory architecture tradeoffs"
        results = self.search(query, limit=evidence_limit)
        chunks = [
            EvidenceChunk(
                id=r.chunk_id,
                source_id=r.source_id,
                chunk_type=r.chunk_type,
                section_path=r.section_path,
                text=r.text,
                pattern_id=r.pattern_id,
            )
            for r in results
        ]
        return ComparisonContext.from_patterns(patterns, evidence_chunks=chunks, comparison_query=query)

    def get_source_section(self, source_id: str, section_path: str = "") -> str:
        doc = self.get_source(source_id)
        if doc is None:
            return ""
        if not section_path and doc.abstract:
            return f"{doc.title}\n\nAbstract\n\n{doc.abstract}"
        for section in doc.sections:
            if section.path == section_path or section.title.lower() == section_path.lower():
                return section.text or section.summary or ""
            for child in section.children:
                if child.path == section_path:
                    return child.text or child.summary or ""
        parts = [doc.title, doc.abstract or ""]
        for section in doc.sections:
            if section.text:
                parts.append(f"## {section.title}\n{section.text[:2000]}")
        return "\n\n".join(p for p in parts if p)

    def search_chunks(self, query: str, tags: list[str] | None = None, limit: int = 10) -> list[EvidenceChunk]:
        return [
            EvidenceChunk(
                id=r.chunk_id,
                source_id=r.source_id,
                chunk_type=r.chunk_type,
                section_path=r.section_path,
                text=r.text,
                pattern_id=r.pattern_id,
            )
            for r in self.search(query, tags=tags, limit=limit)
        ]

    def stats(self) -> MAKStats:
        registry = load_registry()
        taxonomy = load_taxonomy()
        patterns = load_all_patterns()
        pending_reviews = len(self.layout.list_pending_reviews())
        return MAKStats(
            pattern_count=len(patterns),
            source_count=len(registry.sources),
            sources_pending=len(registry.by_status("pending")),
            sources_fetched=len(registry.by_status("fetched")),
            sources_extracted=len(registry.by_status("extracted")),
            sources_failed=len(registry.by_status("failed")),
            document_count=len(self.layout.list_document_ids()),
            indexed_chunks=self.index.count(),
            pending_reviews=pending_reviews,
            taxonomy_axes=len(taxonomy),
        )

    def context_for_profile(self, profile: Any) -> MAKContext:
        """Stub — wired in K7 when AgentProfile exists."""
        query = str(profile)
        results = self.search(query, limit=5)
        chunks = [
            EvidenceChunk(
                id=r.chunk_id,
                source_id=r.source_id,
                chunk_type=r.chunk_type,
                section_path=r.section_path,
                text=r.text,
                pattern_id=r.pattern_id,
            )
            for r in results
        ]
        pattern_ids = {r.pattern_id for r in results if r.pattern_id}
        patterns = [load_pattern(pid) for pid in pattern_ids if pid]
        return MAKContext(chunks=chunks, patterns=patterns)

    def rebuild_index(self) -> int:
        return self.index.rebuild()
