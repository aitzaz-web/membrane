"""Tests for agentic MAK tools and profiling orchestrator."""

from membrane.analyze.orchestrator import ProfilingInput, ProfilingOrchestrator
from membrane.knowledge.tools import MAKToolHandler


def test_mak_tool_search():
    handler = MAKToolHandler()
    result = handler.execute("mak_search", {"query": "vector RAG agent memory", "limit": 3})
    assert "results" in result


def test_mak_tool_compare():
    handler = MAKToolHandler()
    result = handler.execute(
        "mak_compare",
        {"pattern_ids": ["vector_rag", "graphiti"], "focus": "temporal reasoning"},
    )
    assert len(result["patterns"]) == 2
    assert result["pattern_ids"] == ["vector_rag", "graphiti"]


def test_mak_tool_get_pattern():
    handler = MAKToolHandler()
    result = handler.execute("mak_get_pattern", {"pattern_id": "vector_rag"})
    assert result["id"] == "vector_rag"


def test_orchestrator_heuristic_loop():
    orchestrator = ProfilingOrchestrator(max_iterations=6)
    result = orchestrator.run(
        ProfilingInput(
            codebase_bundle={
                "memory_signals": ["alert correlation timeline", "audit_log table"],
                "infra_already_present": ["postgres", "redis"],
                "dependencies": {"runtime": ["chromadb"]},
            },
            product_bundle={
                "product_type": "cybersecurity_agent",
                "feature_list": ["incident investigation", "root cause analysis"],
                "compliance_mentions": ["SOC2"],
            },
            stated_constraints={"latency_p99_ms": 200, "privacy": "on_prem"},
        )
    )
    assert result.mode == "heuristic"
    assert result.iterations >= 1
    assert len(result.scratchpad.tool_calls) >= 1
    assert len(result.scratchpad.mak_chunks) >= 0
    assert "temporal" in result.profile.memory_needs or "audit" in result.profile.memory_needs
    assert result.profile.tool_call_count >= 1
