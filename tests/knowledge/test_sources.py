"""Tests for source registry."""

from membrane.knowledge.configs.sources import SourceEntry, SourceRegistry, arxiv_source_id, normalize_arxiv_id


def test_normalize_arxiv_id():
    assert normalize_arxiv_id("arxiv:2601.03236") == "2601.03236"
    assert normalize_arxiv_id("https://arxiv.org/abs/2601.03236v2") == "2601.03236"


def test_arxiv_source_id():
    assert arxiv_source_id("2601.03236") == "arxiv_2601_03236"


def test_registry_upsert():
    reg = SourceRegistry()
    entry = SourceEntry.from_arxiv_url("https://arxiv.org/abs/2601.03236", title="MAGMA")
    reg.upsert(entry)
    assert reg.get(entry.id) is not None
    reg.upsert(entry.model_copy(update={"status": "fetched"}))
    assert reg.get(entry.id).status == "fetched"
