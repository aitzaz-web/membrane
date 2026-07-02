"""GitHub README fetcher."""

from __future__ import annotations

import base64

import httpx

from membrane.knowledge.configs.sources import url_source_id
from membrane.knowledge.preprocess.raw import RawDocument

USER_AGENT = "membrane-knowledge/0.1"
API_BASE = "https://api.github.com"


def fetch_github_readme(repo: str) -> RawDocument:
    owner, name = repo.split("/", 1)
    url = f"{API_BASE}/repos/{owner}/{name}/readme"
    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        source_id = f"github_{owner}_{name}".lower()
        return RawDocument(
            source_id=source_id,
            source_type="github_readme",
            url=f"https://github.com/{owner}/{name}",
            title=f"{owner}/{name} README",
            mime="text/markdown",
            content=content.encode("utf-8"),
            metadata={"repo": repo, "path": data.get("path", "README.md")},
        )
