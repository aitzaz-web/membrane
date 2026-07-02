"""arXiv fetcher — metadata + PDF download."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import arxiv
import httpx

from membrane.knowledge.configs.sources import arxiv_source_id, normalize_arxiv_id
from membrane.knowledge.preprocess.raw import RawDocument

USER_AGENT = "membrane-knowledge/0.1 (+https://github.com/aitzaz/membrane)"
ARXIV_CLIENT = arxiv.Client(delay_seconds=3.0, num_retries=5)


def parse_arxiv_input(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^arxiv:", "", value, flags=re.IGNORECASE)
    if value.startswith("http"):
        return normalize_arxiv_id(value)
    return normalize_arxiv_id(value)


def _fetch_pdf_with_retry(pdf_url: str, dest: Path, max_attempts: int = 5) -> None:
    for attempt in range(max_attempts):
        with httpx.Client(timeout=120.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(pdf_url)
            if resp.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return
    raise httpx.HTTPStatusError(
        "arXiv PDF rate limited after retries",
        request=httpx.Request("GET", pdf_url),
        response=httpx.Response(429, request=httpx.Request("GET", pdf_url)),
    )


def fetch_arxiv(
    arxiv_id: str,
    cache_dir: Path | None = None,
    title: str | None = None,
    skip_metadata_api: bool = False,
) -> RawDocument:
    arxiv_id = parse_arxiv_input(arxiv_id)
    source_id = arxiv_source_id(arxiv_id)
    cache_dir = cache_dir or Path(".membrane/knowledge/cache/arxiv")
    cache_dir.mkdir(parents=True, exist_ok=True)
    pdf_cache = cache_dir / f"{source_id}.pdf"
    meta_cache = cache_dir / f"{source_id}.meta.json"

    title_resolved = title
    abstract = None
    authors: list[str] = []

    if not skip_metadata_api and meta_cache.exists():
        meta = json.loads(meta_cache.read_text())
        title_resolved = meta.get("title") or title_resolved
        abstract = meta.get("abstract")
        authors = meta.get("authors", [])

    if not pdf_cache.exists():
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        _fetch_pdf_with_retry(pdf_url, pdf_cache)

    if not skip_metadata_api and not meta_cache.exists():
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(ARXIV_CLIENT.results(search), None)
            if paper is not None:
                title_resolved = paper.title
                abstract = paper.summary
                authors = [a.name for a in paper.authors]
                meta_cache.write_text(
                    json.dumps(
                        {
                            "title": title_resolved,
                            "abstract": abstract,
                            "authors": authors,
                            "arxiv_id": arxiv_id,
                            "pdf_url": paper.pdf_url,
                        },
                        indent=2,
                    )
                )
        except Exception:
            # PDF may still be valid; metadata can be filled from document text later
            pass

    if not title_resolved:
        title_resolved = f"arXiv {arxiv_id}"

    return RawDocument(
        source_id=source_id,
        source_type="arxiv_paper",
        url=f"https://arxiv.org/abs/{arxiv_id}",
        title=title_resolved,
        mime="application/pdf",
        content=pdf_cache.read_bytes(),
        metadata={
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "authors": authors,
        },
    )
