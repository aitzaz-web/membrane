"""Parse awesome-list READMEs to discover paper and repo URLs."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from membrane.knowledge.configs.sources import SourceEntry, SourceRegistry, normalize_arxiv_id, url_source_id

USER_AGENT = "membrane-knowledge/0.1"

AWESOME_LISTS = [
    ("FeishuLuo/Evolving-LLM-Agent-Memory-Survey", "evolving_llm_survey"),
    ("TsinghuaC3I/Awesome-Memory-for-Agents", "tsinghua_awesome"),
    ("OpenDataBox/awesome-agent-memory", "opendatabox"),
    ("TeleAI-UAGI/Awesome-Agent-Memory", "teleai"),
    ("yyyujintang/Awesome-Agent-Memory-Papers", "yyyujintang"),
]

ARXIV_RE = re.compile(
    r"https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?",
    re.IGNORECASE,
)
ARXIV_ID_RE = re.compile(r"\barXiv:(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
GITHUB_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def fetch_readme(repo: str, client: httpx.Client | None = None) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/master/README.md"
    own = client is None
    if own:
        client = httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    try:
        resp = client.get(url)
        if resp.status_code == 404:
            url = f"https://raw.githubusercontent.com/{repo}/main/README.md"
            resp = client.get(url)
        resp.raise_for_status()
        return resp.text
    finally:
        if own:
            client.close()


def parse_readme_links(text: str, discovered_from: str) -> list[SourceEntry]:
    entries: list[SourceEntry] = []
    seen: set[str] = set()

    for match in MARKDOWN_LINK_RE.finditer(text):
        title = match.group(1).strip()
        url = match.group(2).strip()
        if url.startswith("#"):
            continue
        year_match = YEAR_RE.search(title)
        year = int(year_match.group(1)) if year_match else None

        arxiv_match = ARXIV_RE.search(url)
        if arxiv_match:
            arxiv_id = normalize_arxiv_id(arxiv_match.group(1))
            key = f"arxiv:{arxiv_id}"
            if key in seen:
                continue
            seen.add(key)
            entry = SourceEntry.from_arxiv_url(
                f"https://arxiv.org/abs/{arxiv_id}",
                title=title,
                year=year,
                discovered_from=discovered_from,
            )
            entries.append(entry)
            continue

        arxiv_id_match = ARXIV_ID_RE.search(title) or ARXIV_ID_RE.search(url)
        if arxiv_id_match:
            arxiv_id = normalize_arxiv_id(arxiv_id_match.group(1))
            key = f"arxiv:{arxiv_id}"
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                SourceEntry.from_arxiv_url(
                    f"https://arxiv.org/abs/{arxiv_id}",
                    title=title,
                    year=year,
                    discovered_from=discovered_from,
                )
            )
            continue

        gh_match = GITHUB_RE.search(url)
        if gh_match:
            repo = gh_match.group(1).rstrip("/")
            if repo.lower().endswith("/issues") or "/tree/" in url:
                continue
            key = f"github:{repo.lower()}"
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                SourceEntry(
                    id=f"github_{repo.replace('/', '_').lower()}",
                    type="github_readme",
                    url=f"https://github.com/{repo}",
                    github_url=f"https://github.com/{repo}",
                    title=title,
                    year=year,
                    discovered_from=discovered_from,
                )
            )

    # Also scan bare arXiv URLs in text
    for match in ARXIV_RE.finditer(text):
        arxiv_id = normalize_arxiv_id(match.group(1))
        key = f"arxiv:{arxiv_id}"
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            SourceEntry.from_arxiv_url(
                f"https://arxiv.org/abs/{arxiv_id}",
                discovered_from=discovered_from,
            )
        )

    return entries


def sync_awesome_lists(registry: SourceRegistry | None = None) -> tuple[int, int]:
    registry = registry or SourceRegistry()
    existing_keys = {registry.dedupe_key(s) for s in registry.sources}
    added = 0
    total_found = 0

    with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for repo, label in AWESOME_LISTS:
            try:
                readme = fetch_readme(repo, client=client)
            except Exception:
                continue
            entries = parse_readme_links(readme, discovered_from=label)
            total_found += len(entries)
            for entry in entries:
                key = registry.dedupe_key(entry)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                registry.upsert(entry)
                added += 1

    return added, total_found
