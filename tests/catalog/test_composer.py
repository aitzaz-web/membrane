"""Tests for hybrid architecture composition."""

from membrane.catalog.composer import compose_candidates, greedy_compose_hybrid, load_recipe
from membrane.schemas.hybrid import HybridArchitecture


def test_greedy_compose_covers_needs():
    hybrid = greedy_compose_hybrid(
        memory_needs=["temporal", "entity", "semantic", "audit"],
        query_patterns=["temporal_reasoning", "similarity_lookup"],
    )
    assert isinstance(hybrid, HybridArchitecture)
    assert hybrid.type == "hybrid"
    assert len(hybrid.components) >= 2
    covered = {n for c in hybrid.components for n in c.serves}
    assert "semantic" in covered or "temporal" in covered


def test_compose_candidates_includes_baseline_and_hybrid():
    candidates = compose_candidates(
        memory_needs=["temporal", "causal", "entity", "semantic"],
        query_patterns=["temporal_reasoning", "causal_chains"],
        product_type="cybersecurity_agent",
        max_candidates=5,
    )
    types = {c.type for c in candidates}
    assert "monolithic" in types
    assert "hybrid" in types
    ids = [c.id for c in candidates]
    assert "vector_rag" in ids


def test_load_cyber_recipe():
    recipe = load_recipe("cybersecurity_soc_stack")
    assert recipe.type == "hybrid"
    assert len(recipe.components) == 3
    roles = {c.role for c in recipe.components}
    assert "incident_graph" in roles
    assert recipe.router.default_role == "session_memory"
