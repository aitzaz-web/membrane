"""Review queue — approve/reject extractions into catalog."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from membrane.catalog.loader import (
    ArchitecturePattern,
    PatternConstraints,
    PatternEvalAffinities,
    PatternImplementation,
    PatternSource,
    load_pattern,
    save_pattern,
)
from membrane.knowledge.configs.sources import load_registry, save_registry
from membrane.knowledge.models.extraction import ArchitectureExtraction
from membrane.knowledge.storage.layout import KnowledgeLayout


def _slug_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:50]


def extraction_to_pattern(
    extraction: ArchitectureExtraction,
    source_id: str,
    source_url: str | None,
    pattern_id: str | None = None,
) -> ArchitecturePattern:
    pid = pattern_id or extraction.suggested_pattern_id or _slug_id(extraction.name)
    structures = [t for t in extraction.taxonomy_tags if t in ("vector", "graph", "multi_graph", "tree")]
    if not structures and "graph" in extraction.taxonomy_tags:
        structures = ["single_graph"]
    if not structures:
        structures = ["vector_index"]

    return ArchitecturePattern(
        id=pid,
        name=extraction.name,
        version="1.0",
        sources=[
            PatternSource(type="paper", source_id=source_id, url=source_url),
        ],
        taxonomy={
            "structures": structures,
            "memory_types": extraction.memory_needs_served[:3] or ["semantic"],
        },
        memory_needs_served=extraction.memory_needs_served,
        query_patterns_served=extraction.query_patterns_served,
        components=extraction.components,
        infra_requirements=[{"type": r} for r in extraction.infra_requirements],
        constraints=PatternConstraints(
            latency_profile="medium",
            cost_profile="medium",
            privacy="self_hostable" if extraction.implementation_available else "cloud_ok",
            explainability="high" if "graph" in extraction.taxonomy_tags else "medium",
        ),
        eval_affinities=PatternEvalAffinities(
            excels_at=extraction.strengths[:3],
            weak_at=extraction.weaknesses[:3],
        ),
        composable_with=extraction.comparable_to,
        implementation=PatternImplementation(
            adapter=f"adapters.{pid}",
            reference_impl="adapters.vector_rag_lite",
        )
        if extraction.implementation_available
        else None,
        one_line_summary=extraction.one_line_summary,
        strengths=extraction.strengths,
        weaknesses=extraction.weaknesses,
        reported_metrics=extraction.reported_metrics,
    )


def approve_extraction(
    extraction_id: str,
    pattern_id: str | None = None,
    layout: KnowledgeLayout | None = None,
) -> ArchitecturePattern:
    layout = layout or KnowledgeLayout()
    item = layout.load_review_item(extraction_id, "pending")
    if item is None:
        raise ValueError(f"Pending review not found: {extraction_id}")

    extraction = ArchitectureExtraction.model_validate(item["extraction"])
    if not extraction.evidence_quotes:
        raise ValueError("Cannot approve extraction without evidence_quotes")

    pattern = extraction_to_pattern(
        extraction,
        source_id=item["source_id"],
        source_url=item.get("source_url"),
        pattern_id=pattern_id or extraction.suggested_pattern_id,
    )

    # Merge with existing pattern if present
    try:
        existing = load_pattern(pattern.id)
        merged_sources = list(existing.sources)
        new_source = pattern.sources[0]
        if not any(s.source_id == new_source.source_id for s in merged_sources):
            merged_sources.append(new_source)
        pattern = existing.model_copy(
            update={
                "sources": merged_sources,
                "one_line_summary": pattern.one_line_summary or existing.one_line_summary,
                "strengths": pattern.strengths or existing.strengths,
                "weaknesses": pattern.weaknesses or existing.weaknesses,
                "reported_metrics": {**existing.reported_metrics, **pattern.reported_metrics},
            }
        )
    except FileNotFoundError:
        pass

    save_pattern(pattern)
    layout.move_review(extraction_id, "approved")

    item["approved_at"] = datetime.now(timezone.utc).isoformat()
    item["pattern_id"] = pattern.id
    layout.review_path(extraction_id, "approved").write_text(
        __import__("json").dumps(item, indent=2, default=str)
    )

    registry = load_registry()
    entry = registry.get(item["source_id"])
    if entry and pattern.id not in entry.pattern_ids:
        entry.pattern_ids.append(pattern.id)
        registry.upsert(entry)
        save_registry(registry)

    return pattern


def reject_extraction(extraction_id: str, layout: KnowledgeLayout | None = None) -> None:
    layout = layout or KnowledgeLayout()
    layout.move_review(extraction_id, "rejected")
