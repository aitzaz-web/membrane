"""LLM structured extraction for architecture knowledge."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone

from openai import OpenAI

from membrane.knowledge.models.extraction import ArchitectureExtraction
from membrane.knowledge.models.knowledge import SourceDocument
from membrane.knowledge.storage.layout import KnowledgeLayout

EXTRACTION_PROMPT = """You are extracting memory architecture knowledge from a source document.
Return structured JSON matching the ArchitectureExtraction schema.

Focus on: architecture name, memory types, write/read paths, components, infra requirements,
reported benchmark metrics, strengths/weaknesses, and direct evidence quotes from the text.

Source title: {title}
Source type: {source_type}

Document text (truncated):
{text}
"""


def _slug_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:50]


def _document_text(doc: SourceDocument, max_chars: int = 12000) -> str:
    parts = [doc.title, doc.abstract or ""]
    for section in doc.sections:
        if section.text:
            parts.append(f"## {section.title}\n{section.text[:2000]}")
    text = "\n\n".join(p for p in parts if p)
    return text[:max_chars]


def extract_architecture(
    doc: SourceDocument,
    model: str | None = None,
    client: OpenAI | None = None,
) -> ArchitectureExtraction:
    model = model or os.environ.get("MEMBRANE_LLM_MODEL", "gpt-4o-mini")
    api_key = os.environ.get("MEMBRANE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")

    text = _document_text(doc)

    if not api_key:
        return _heuristic_extraction(doc, text)

    if client is None:
        base_url = os.environ.get("MEMBRANE_LLM_BASE_URL")
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    prompt = EXTRACTION_PROMPT.format(
        title=doc.title,
        source_type=doc.source.source_type,
        text=text,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You extract memory architecture facts. Respond with valid JSON only."},
            {"role": "user", "content": prompt + "\n\nJSON schema fields: " + json.dumps(ArchitectureExtraction.model_json_schema())},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    extraction = ArchitectureExtraction.model_validate(data)
    if not extraction.suggested_pattern_id:
        extraction.suggested_pattern_id = _slug_id(extraction.name)
    return extraction


def _heuristic_extraction(doc: SourceDocument, text: str) -> ArchitectureExtraction:
    """Fallback when no LLM API key is configured."""
    name = doc.title
    lower = text.lower()
    tags: list[str] = []
    needs: list[str] = []
    if "temporal" in lower or "time" in lower:
        tags.append("temporal")
        needs.append("temporal")
    if "graph" in lower:
        tags.append("graph")
    if "vector" in lower or "embedding" in lower:
        tags.append("vector")
        needs.append("semantic")
    if "causal" in lower:
        tags.append("causal")
        needs.append("causal")

    quotes = []
    if doc.abstract:
        quotes.append(doc.abstract[:300])

    return ArchitectureExtraction(
        name=name,
        one_line_summary=doc.abstract[:200] if doc.abstract else name[:200],
        taxonomy_tags=tags,
        memory_needs_served=needs or ["semantic"],
        query_patterns_served=["similarity_lookup"],
        components=[],
        write_path="unknown",
        read_path="unknown",
        confidence=0.3,
        evidence_quotes=quotes,
        suggested_pattern_id=_slug_id(name),
    )


def extract_and_queue(
    source_id: str,
    layout: KnowledgeLayout | None = None,
    model: str | None = None,
) -> str:
    layout = layout or KnowledgeLayout()
    doc = layout.load_document(source_id)
    if doc is None:
        raise ValueError(f"No document for source: {source_id}")

    extraction = extract_architecture(doc, model=model)
    extraction_id = f"ext_{uuid.uuid4().hex[:12]}"

    item = {
        "extraction_id": extraction_id,
        "source_id": source_id,
        "source_title": doc.title,
        "source_url": doc.source.url,
        "extraction": extraction.model_dump(mode="json"),
        "model": model or os.environ.get("MEMBRANE_LLM_MODEL", "heuristic"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    layout.save_review_item(item)
    return extraction_id


def batch_extract_pending(
    concurrency: int = 2,
    layout: KnowledgeLayout | None = None,
    registry=None,
) -> tuple[int, int]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from membrane.knowledge.configs.sources import load_registry, save_registry

    layout = layout or KnowledgeLayout()
    registry = registry or load_registry()
    pending = [s for s in registry.sources if s.status == "fetched"]

    success = 0
    failed = 0

    def _extract_one(entry):
        extract_and_queue(entry.id, layout=layout)
        return entry.model_copy(
            update={"status": "extracted", "extracted_at": datetime.now(timezone.utc)}
        )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(_extract_one, e): e for e in pending}
        for future in as_completed(futures):
            try:
                updated = future.result()
                registry.upsert(updated)
                success += 1
            except Exception as e:
                entry = futures[future]
                registry.upsert(entry.model_copy(update={"status": "failed", "error": str(e)}))
                failed += 1

    save_registry(registry)
    return success, failed
