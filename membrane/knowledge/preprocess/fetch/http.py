"""Generic HTTP fetcher with disk cache."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from membrane.knowledge.preprocess.raw import RawDocument
from membrane.knowledge.configs.sources import url_source_id


DEFAULT_TIMEOUT = 60.0
USER_AGENT = "membrane-knowledge/0.1 (+https://github.com/aitzaz/membrane)"


def _cache_path(url: str, cache_dir: Path) -> Path:
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    return cache_dir / key


def fetch_url(
    url: str,
    source_id: str | None = None,
    source_type: str = "http",
    cache_dir: Path | None = None,
    client: httpx.Client | None = None,
) -> RawDocument:
    cache_dir = cache_dir or Path(".membrane/knowledge/cache/http")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(url, cache_dir)

    if cache_file.exists():
        data = cache_file.read_bytes()
        meta_file = cache_file.with_suffix(".meta")
        mime = "text/html"
        title = None
        if meta_file.exists():
            import json

            meta = json.loads(meta_file.read_text())
            mime = meta.get("mime", mime)
            title = meta.get("title")
        return RawDocument(
            source_id=source_id or url_source_id(url),
            source_type=source_type,
            url=url,
            title=title,
            mime=mime,
            content=data,
        )

    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    try:
        resp = client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
        cache_file.write_bytes(resp.content)
        import json

        meta = {"mime": content_type, "title": None, "url": url}
        cache_file.with_suffix(".meta").write_text(json.dumps(meta))
        return RawDocument(
            source_id=source_id or url_source_id(url),
            source_type=source_type,
            url=url,
            mime=content_type,
            content=resp.content,
        )
    finally:
        if own_client:
            client.close()
