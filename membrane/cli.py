"""Membrane CLI — knowledge commands."""

from __future__ import annotations

import json
import re

import typer
from rich.console import Console
from rich.table import Table

from membrane.catalog.loader import load_pattern, load_taxonomy
from membrane.knowledge.client import MAKClient
from membrane.knowledge.configs.sources import load_registry, save_registry
from membrane.knowledge.extract.extractor import extract_and_queue
from membrane.knowledge.flows.batch_ingest import batch_fetch_pending
from membrane.knowledge.flows.paper_flow import ingest_raw_document
from membrane.knowledge.preprocess.fetch.arxiv import fetch_arxiv, parse_arxiv_input
from membrane.knowledge.preprocess.fetch.http import fetch_url
from membrane.knowledge.review.queue import approve_extraction, reject_extraction
from membrane.knowledge.storage.layout import KnowledgeLayout
from membrane.knowledge.sync.awesome_parser import sync_awesome_lists

app = typer.Typer(no_args_is_help=True, help="Membrane — memory architecture platform.")
knowledge_app = typer.Typer(no_args_is_help=True, help="Memory Architecture Knowledge Base commands.")
review_app = typer.Typer(no_args_is_help=True, help="Review extraction queue.")
knowledge_app.add_typer(review_app, name="review")
app.add_typer(knowledge_app, name="knowledge")

console = Console()


def _client() -> MAKClient:
    return MAKClient()


@knowledge_app.command("stats")
def knowledge_stats() -> None:
    """Show taxonomy, catalog, registry, and index stats."""
    client = _client()
    stats = client.stats()
    taxonomy = load_taxonomy()

    table = Table(title="Membrane MAK Stats")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Catalog patterns", str(stats.pattern_count))
    table.add_row("Taxonomy axes", str(stats.taxonomy_axes))
    table.add_row("Registry sources (total)", str(stats.source_count))
    table.add_row("  pending", str(stats.sources_pending))
    table.add_row("  fetched", str(stats.sources_fetched))
    table.add_row("  extracted", str(stats.sources_extracted))
    table.add_row("  failed", str(stats.sources_failed))
    table.add_row("Corpus documents", str(stats.document_count))
    table.add_row("Indexed chunks", str(stats.indexed_chunks))
    table.add_row("Pending reviews", str(stats.pending_reviews))
    console.print(table)

    console.print("\n[bold]Taxonomy axes:[/bold]")
    for axis, values in taxonomy.items():
        if isinstance(values, list):
            console.print(f"  {axis}: {', '.join(values[:8])}{'...' if len(values) > 8 else ''}")
        elif isinstance(values, dict):
            console.print(f"  {axis}: {values}")


@knowledge_app.command("ingest")
def knowledge_ingest(
    target: str = typer.Argument(..., help="arxiv:ID, URL, or source_id"),
) -> None:
    """Fetch and ingest a single source."""
    layout = KnowledgeLayout()
    layout.ensure_dirs()
    registry = load_registry()

    if target.lower().startswith("arxiv:") or re.match(r"^\d{4}\.\d{4,5}", target):
        arxiv_id = parse_arxiv_input(target)
        raw = fetch_arxiv(arxiv_id)
    elif target.startswith("http"):
        raw = fetch_url(target)
    else:
        raise typer.BadParameter("Provide arxiv:ID or http(s) URL")

    doc, chunks = ingest_raw_document(raw, layout=layout)
    from membrane.knowledge.configs.sources import SourceEntry

    entry = SourceEntry(
        id=raw.source_id,
        type="arxiv_paper" if raw.source_type == "arxiv_paper" else "http",
        url=raw.url,
        title=doc.title,
        arxiv_id=raw.metadata.get("arxiv_id"),
        status="fetched",
    )
    registry.upsert(entry)
    save_registry(registry)

    console.print(f"[green]Ingested[/green] {doc.title}")
    console.print(f"  source_id: {raw.source_id}")
    console.print(f"  sections: {len(doc.sections)}")
    console.print(f"  chunks: {len(chunks)}")


@knowledge_app.command("show")
def knowledge_show(
    kind: str = typer.Argument(..., help="source or pattern"),
    identifier: str = typer.Argument(..., help="source_id or pattern_id"),
) -> None:
    """Show a source document tree or catalog pattern."""
    client = _client()

    if kind == "pattern":
        pattern = load_pattern(identifier)
        console.print_json(pattern.model_dump_json(indent=2))
        return

    if kind == "source":
        doc = client.get_source(identifier)
        if doc is None:
            raise typer.Exit(code=1)
        console.print(f"[bold]{doc.title}[/bold]")
        if doc.abstract:
            console.print(f"\nAbstract: {doc.abstract[:500]}...")
        console.print(f"\nSections ({len(doc.sections)}):")
        for section in doc.sections:
            preview = (section.text or section.summary or "")[:120]
            console.print(f"  - {section.title} ({section.path}): {preview}...")
        return

    raise typer.BadParameter("kind must be 'source' or 'pattern'")


@knowledge_app.command("sync")
def knowledge_sync(
    target: str = typer.Argument("awesome-lists", help="awesome-lists"),
) -> None:
    """Sync source feeds into the registry."""
    if target != "awesome-lists":
        raise typer.BadParameter("Only 'awesome-lists' is supported in v1")

    registry = load_registry()
    added, total = sync_awesome_lists(registry)
    save_registry(registry)
    console.print(f"[green]Synced awesome lists[/green]: {added} new sources ({total} links parsed)")


@knowledge_app.command("fetch")
def knowledge_fetch(
    pending: bool = typer.Option(True, "--pending/--all", help="Fetch pending sources only"),
    concurrency: int = typer.Option(4, "--concurrency", "-c"),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max sources to fetch"),
    source_type: str | None = typer.Option(None, "--type", "-t", help="Filter by type, e.g. arxiv_paper"),
    retry_failed: bool = typer.Option(False, "--retry-failed", help="Include previously failed sources"),
) -> None:
    """Batch fetch and parse pending sources."""
    if not pending:
        raise typer.BadParameter("--all not supported; use --pending")
    success, failed = batch_fetch_pending(
        concurrency=concurrency,
        limit=limit,
        source_type=source_type,
        retry_failed=retry_failed,
    )
    console.print(f"[green]Fetched[/green] {success} sources, [red]{failed}[/red] failed")


@knowledge_app.command("extract")
def knowledge_extract(
    pending: bool = typer.Option(True, "--pending/--id"),
    source_id: str | None = typer.Option(None, "--source-id"),
    concurrency: int = typer.Option(2, "--concurrency", "-c"),
) -> None:
    """Run LLM extraction on fetched sources."""
    if source_id:
        ext_id = extract_and_queue(source_id)
        console.print(f"[green]Queued extraction[/green] {ext_id}")
        return

    if pending:
        from membrane.knowledge.extract.extractor import batch_extract_pending

        success, failed = batch_extract_pending(concurrency=concurrency)
        console.print(f"[green]Extracted[/green] {success} sources, [red]{failed}[/red] failed")
        return

    raise typer.BadParameter("Use --pending or --source-id")


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n"),
) -> None:
    """Semantic search over the knowledge corpus."""
    client = _client()
    results = client.search(query, limit=limit)
    if not results:
        console.print("[yellow]No results. Run 'membrane knowledge index --rebuild' first.[/yellow]")
        return

    for i, r in enumerate(results, 1):
        console.print(f"\n[bold]{i}. score={r.score:.3f}[/bold] [{r.chunk_type}] {r.source_id}/{r.section_path}")
        console.print(r.text[:400] + ("..." if len(r.text) > 400 else ""))


@knowledge_app.command("index")
def knowledge_index(
    rebuild: bool = typer.Option(False, "--rebuild"),
) -> None:
    """Build or rebuild the vector index."""
    if not rebuild:
        raise typer.BadParameter("Use --rebuild to build the index")
    client = _client()
    count = client.rebuild_index()
    console.print(f"[green]Indexed[/green] {count} chunks")


@review_app.command("list")
def review_list() -> None:
    """List pending extractions."""
    layout = KnowledgeLayout()
    items = layout.list_pending_reviews()
    if not items:
        console.print("No pending reviews.")
        return

    table = Table(title="Pending Reviews")
    table.add_column("ID")
    table.add_column("Source")
    table.add_column("Name")
    table.add_column("Confidence")
    for item in items:
        ext = item.get("extraction", {})
        conf = ext.get("confidence", 0)
        flag = " [red]LOW[/red]" if conf < 0.5 else ""
        table.add_row(
            item["extraction_id"],
            item.get("source_id", ""),
            ext.get("name", "")[:40],
            f"{conf:.2f}{flag}",
        )
    console.print(table)


@review_app.command("approve")
def review_approve(
    extraction_id: str = typer.Argument(...),
    pattern_id: str | None = typer.Option(None, "--pattern-id"),
) -> None:
    """Approve extraction → catalog pattern YAML."""
    pattern = approve_extraction(extraction_id, pattern_id=pattern_id)
    console.print(f"[green]Approved[/green] → catalog/patterns/{pattern.id}.yaml")


@review_app.command("reject")
def review_reject(extraction_id: str = typer.Argument(...)) -> None:
    """Reject a pending extraction."""
    reject_extraction(extraction_id)
    console.print(f"[yellow]Rejected[/yellow] {extraction_id}")


if __name__ == "__main__":
    app()
