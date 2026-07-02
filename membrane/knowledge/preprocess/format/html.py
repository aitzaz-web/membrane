"""HTML to markdown via trafilatura."""

from __future__ import annotations

import trafilatura

from membrane.knowledge.preprocess.raw import RawDocument


def parse_html(raw: RawDocument) -> tuple[str, str | None]:
    html = raw.content.decode("utf-8", errors="replace")
    markdown = trafilatura.extract(html, output_format="markdown", include_links=True) or ""
    title = trafilatura.extract_metadata(html).title if html else None
    return markdown, title
