"""Batch ingest — fetch and parse pending sources with concurrency."""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone

from membrane.knowledge.configs.sources import SourceEntry, SourceRegistry, load_registry, save_registry
from membrane.knowledge.flows.paper_flow import ingest_raw_document
from membrane.knowledge.preprocess.fetch.arxiv import fetch_arxiv
from membrane.knowledge.preprocess.fetch.github import fetch_github_readme
from membrane.knowledge.preprocess.fetch.http import fetch_url
from membrane.knowledge.preprocess.raw import RawDocument
from membrane.knowledge.storage.layout import KnowledgeLayout


def fetch_source(entry: SourceEntry) -> RawDocument:
    if entry.type == "arxiv_paper" and entry.arxiv_id:
        return fetch_arxiv(entry.arxiv_id, title=entry.title, skip_metadata_api=True)
    if entry.type == "github_readme" and entry.github_url:
        repo = entry.github_url.rstrip("/").split("github.com/")[-1]
        return fetch_github_readme(repo)
    return fetch_url(entry.url, source_id=entry.id, source_type=entry.type)


def process_source(entry: SourceEntry, layout: KnowledgeLayout) -> SourceEntry:
    try:
        raw = fetch_source(entry)
        ingest_raw_document(raw, layout=layout)
        return entry.model_copy(
            update={
                "status": "fetched",
                "fetched_at": datetime.now(timezone.utc),
                "title": raw.title or entry.title,
                "error": None,
            }
        )
    except Exception as e:
        return entry.model_copy(update={"status": "failed", "error": str(e)})


def batch_fetch_pending(
    concurrency: int = 4,
    layout: KnowledgeLayout | None = None,
    registry: SourceRegistry | None = None,
    limit: int | None = None,
    source_type: str | None = None,
    retry_failed: bool = False,
) -> tuple[int, int]:
    layout = layout or KnowledgeLayout()
    layout.ensure_dirs()
    registry = registry or load_registry()
    pending = registry.by_status("pending")
    if retry_failed:
        pending = pending + registry.by_status("failed")
    if source_type:
        pending = [s for s in pending if s.type == source_type]
    if limit is not None:
        pending = pending[:limit]

    # arXiv PDF downloads tolerate modest parallelism; metadata API does not
    if source_type == "arxiv_paper" and concurrency > 4:
        concurrency = 4

    success = 0
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_source, entry, layout): entry for entry in pending}
        for future in concurrent.futures.as_completed(futures):
            updated = future.result()
            registry.upsert(updated)
            if updated.status == "fetched":
                success += 1
            else:
                failed += 1

    save_registry(registry)
    return success, failed
