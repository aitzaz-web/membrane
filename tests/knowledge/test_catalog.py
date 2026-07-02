"""Tests for catalog loader."""

from membrane.catalog.loader import list_pattern_ids, load_pattern, load_taxonomy


def test_list_patterns():
    ids = list_pattern_ids()
    assert len(ids) >= 8
    assert "magma_multigraph" in ids
    assert "vector_rag" in ids


def test_load_pattern():
    pattern = load_pattern("magma_multigraph")
    assert pattern.id == "magma_multigraph"
    assert "temporal" in pattern.memory_needs_served


def test_load_taxonomy():
    taxonomy = load_taxonomy()
    assert "memory_needs" in taxonomy
    assert "temporal" in taxonomy["memory_needs"]
