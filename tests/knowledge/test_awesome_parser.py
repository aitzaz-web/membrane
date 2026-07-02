"""Tests for awesome list parser."""

from membrane.knowledge.sync.awesome_parser import parse_readme_links

SAMPLE_README = """
# Awesome Agent Memory

## Papers

- [MAGMA: Multi-Graph Memory](https://arxiv.org/abs/2601.03236) (2026)
- [A-MEM Agentic Memory](https://arxiv.org/pdf/2502.12110.pdf)
- [MemVerse](https://arxiv.org/abs/2412.04470) arXiv:2412.04470
- [Graphiti Code](https://github.com/getzep/graphiti) — temporal graph
- [Survey](https://github.com/FeishuLuo/Evolving-LLM-Agent-Memory-Survey)
"""


def test_parse_readme_links_arxiv():
    entries = parse_readme_links(SAMPLE_README, discovered_from="test")
    arxiv_ids = {e.arxiv_id for e in entries if e.arxiv_id}
    assert "2601.03236" in arxiv_ids
    assert "2502.12110" in arxiv_ids
    assert "2412.04470" in arxiv_ids


def test_parse_readme_links_github():
    entries = parse_readme_links(SAMPLE_README, discovered_from="test")
    github = [e for e in entries if e.type == "github_readme"]
    repos = {e.github_url for e in github}
    assert any("graphiti" in (u or "") for u in repos)


def test_dedupe_arxiv():
    entries = parse_readme_links(SAMPLE_README, discovered_from="test")
    arxiv_entries = [e for e in entries if e.arxiv_id == "2412.04470"]
    assert len(arxiv_entries) == 1
