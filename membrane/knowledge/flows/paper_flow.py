"""Paper flow — RawDocument to SourceDocument + EvidenceChunks."""

from __future__ import annotations

import re
import uuid

from membrane.knowledge.models.knowledge import EvidenceChunk, SectionNode, SourceDocument
from membrane.knowledge.models.provenance import SourceRef
from membrane.knowledge.preprocess.format.pdf import parse_pdf, split_sections
from membrane.knowledge.preprocess.format.markdown import parse_markdown
from membrane.knowledge.preprocess.format.html import parse_html
from membrane.knowledge.preprocess.raw import RawDocument
from membrane.knowledge.storage.layout import KnowledgeLayout


def _slug_path(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:60] or "section"


def raw_to_source_document(raw: RawDocument) -> tuple[SourceDocument, list[EvidenceChunk]]:
    source_ref = SourceRef(
        source_id=raw.source_id,
        source_type=raw.source_type,
        url=raw.url,
        title=raw.title,
    )

    abstract = raw.metadata.get("abstract")
    title = raw.title or raw.source_id
    sections: list[SectionNode] = []
    chunks: list[EvidenceChunk] = []

    if raw.mime == "application/pdf":
        full_text, _pages = parse_pdf(raw)
        if not abstract:
            abstract_match = re.search(
                r"(?is)abstract[:\s]*(.+?)(?:\n\s*(?:1\.?\s*)?introduction|\n\s*keywords)",
                full_text,
            )
            if abstract_match:
                abstract = abstract_match.group(1).strip()[:2000]

        seen_paths: dict[str, int] = {}
        for sec_title, sec_text in split_sections(full_text):
            base_path = _slug_path(sec_title)
            count = seen_paths.get(base_path, 0)
            seen_paths[base_path] = count + 1
            path = base_path if count == 0 else f"{base_path}_{count}"
            if len(sec_text) < 50:
                continue
            sections.append(SectionNode(title=sec_title, path=path, text=sec_text[:8000]))
            chunks.append(
                EvidenceChunk(
                    id=f"{raw.source_id}_{path}",
                    source_id=raw.source_id,
                    chunk_type="section",
                    section_path=path,
                    text=f"{sec_title}\n\n{sec_text[:4000]}",
                )
            )
    elif raw.mime == "text/markdown":
        _full, md_sections = parse_markdown(raw)
        for sec_title, sec_text in md_sections:
            path = _slug_path(sec_title)
            sections.append(SectionNode(title=sec_title, path=path, text=sec_text[:8000]))
            if len(sec_text) >= 15:
                chunks.append(
                    EvidenceChunk(
                        id=f"{raw.source_id}_{path}",
                        source_id=raw.source_id,
                        chunk_type="section",
                        section_path=path,
                        text=f"{sec_title}\n\n{sec_text[:4000]}",
                    )
                )
    elif "html" in raw.mime:
        markdown, html_title = parse_html(raw)
        if html_title and not title:
            title = html_title
        path = "content"
        sections.append(SectionNode(title="Content", path=path, text=markdown[:8000]))
        if markdown:
            chunks.append(
                EvidenceChunk(
                    id=f"{raw.source_id}_{path}",
                    source_id=raw.source_id,
                    chunk_type="section",
                    section_path=path,
                    text=markdown[:4000],
                )
            )
    else:
        text = raw.text_hint or raw.content.decode("utf-8", errors="replace")
        path = "body"
        sections.append(SectionNode(title="Body", path=path, text=text[:8000]))
        chunks.append(
            EvidenceChunk(
                id=f"{raw.source_id}_{path}",
                source_id=raw.source_id,
                chunk_type="section",
                section_path=path,
                text=text[:4000],
            )
        )

    if abstract:
        chunks.insert(
            0,
            EvidenceChunk(
                id=f"{raw.source_id}_abstract",
                source_id=raw.source_id,
                chunk_type="abstract",
                section_path="abstract",
                text=f"Abstract\n\n{abstract}",
            ),
        )

    doc = SourceDocument(
        id=str(uuid.uuid4()),
        source=source_ref,
        title=title,
        abstract=abstract,
        sections=sections,
        tags=[],
    )
    return doc, chunks


def ingest_raw_document(
    raw: RawDocument,
    layout: KnowledgeLayout | None = None,
) -> tuple[SourceDocument, list[EvidenceChunk]]:
    layout = layout or KnowledgeLayout()
    layout.ensure_dirs()
    layout.raw_path(raw.source_id, raw.mime.split("/")[-1]).write_bytes(raw.content)
    doc, chunks = raw_to_source_document(raw)
    layout.save_document(doc)
    layout.save_chunks(raw.source_id, chunks)
    return doc, chunks
