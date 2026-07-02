"""Agentic profiling orchestrator — iterative MAK queries while analyzing inputs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from membrane.analyze.scratchpad import CodeObservation, Hypothesis, InvestigationScratchpad
from membrane.knowledge.tools import MAKToolHandler
from membrane.schemas.profile import ProfileDraft


@dataclass
class ProfilingInput:
    codebase_bundle: dict[str, Any] | None = None
    product_bundle: dict[str, Any] | None = None
    stated_constraints: dict[str, Any] | None = None
    sample_traces: list[dict[str, Any]] | None = None


@dataclass
class ProfilingResult:
    profile: ProfileDraft
    scratchpad: InvestigationScratchpad
    iterations: int = 0
    mode: str = "heuristic"


class ProfilingOrchestrator:
    """
    Coordinate codebase analysis and MAK research with iterative tool use.

    v1 modes:
    - heuristic: rule-triggered searches (no API key, tests + offline dev)
    - agentic: LLM tool-calling loop when MEMBRANE_LLM_API_KEY is set
  """

    def __init__(
        self,
        mak_tools: MAKToolHandler | None = None,
        max_iterations: int = 8,
        model: str | None = None,
    ) -> None:
        self.mak_tools = mak_tools or MAKToolHandler()
        self.max_iterations = max_iterations
        self.model = model or os.environ.get("MEMBRANE_LLM_MODEL", "gpt-4o-mini")

    def run(self, inputs: ProfilingInput) -> ProfilingResult:
        scratchpad = InvestigationScratchpad()
        self._seed_bundles(inputs, scratchpad)

        api_key = os.environ.get("MEMBRANE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if api_key:
            iterations = self._run_agentic_loop(inputs, scratchpad, api_key)
            mode = "agentic"
        else:
            iterations = self._run_heuristic_loop(scratchpad)
            mode = "heuristic"

        profile = self._synthesize_profile(inputs, scratchpad)
        return ProfilingResult(profile=profile, scratchpad=scratchpad, iterations=iterations, mode=mode)

    def _seed_bundles(self, inputs: ProfilingInput, scratchpad: InvestigationScratchpad) -> None:
        if inputs.codebase_bundle:
            for sig in inputs.codebase_bundle.get("memory_signals", []):
                scratchpad.add_signal(str(sig), "codebase")
            for dep in inputs.codebase_bundle.get("dependencies", {}).get("runtime", []):
                scratchpad.add_signal(f"dependency:{dep}", "codebase")
            for infra in inputs.codebase_bundle.get("infra_already_present", []):
                scratchpad.add_signal(f"infra:{infra}", "codebase")
                scratchpad.code_observations.append(
                    CodeObservation(agent="codebase", kind="infra", text=infra)
                )
        if inputs.product_bundle:
            for feat in inputs.product_bundle.get("feature_list", []):
                scratchpad.add_signal(str(feat), "product")
            for tag in inputs.product_bundle.get("compliance_mentions", []):
                scratchpad.add_signal(f"compliance:{tag}", "product")

    def _run_heuristic_loop(self, scratchpad: InvestigationScratchpad) -> int:
        """Trigger MAK searches from collected signals — mimics human research flow."""
        queries: list[str] = []
        signals = " ".join(scratchpad.codebase_signals + scratchpad.product_signals).lower()

        if any(k in signals for k in ("temporal", "timeline", "incident", "alert")):
            queries.append("temporal graph agent memory incident correlation")
        if any(k in signals for k in ("causal", "root cause", "why")):
            queries.append("causal reasoning memory architecture agent")
        if any(k in signals for k in ("audit", "compliance", "soc2", "hipaa")):
            queries.append("audit provenance memory explainability agent")
        if any(k in signals for k in ("chroma", "vector", "embedding", "qdrant")):
            queries.append("vector RAG vs graph memory tradeoffs agents")
        if not queries:
            queries.append("LLM agent memory architecture survey")

        iterations = 0
        for query in queries[: self.max_iterations]:
            result = self.mak_tools.execute("mak_search", {"query": query, "limit": 6})
            chunks = self.mak_tools.result_to_chunks("mak_search", result)
            scratchpad.add_chunks(chunks)
            scratchpad.record_tool(
                agent="mak_research",
                tool="mak_search",
                arguments={"query": query},
                summary=f"{len(chunks)} chunks",
            )
            iterations += 1

        if "temporal" in signals or "causal" in signals:
            result = self.mak_tools.execute(
                "mak_compare",
                {
                    "pattern_ids": ["vector_rag", "graphiti", "magma_multigraph"],
                    "focus": "temporal and causal reasoning for security agents",
                },
            )
            scratchpad.add_chunks(self.mak_tools.result_to_chunks("mak_compare", result))
            scratchpad.record_tool(
                agent="mak_research",
                tool="mak_compare",
                arguments={"pattern_ids": ["vector_rag", "graphiti", "magma_multigraph"]},
                summary="compared graph vs vector patterns",
            )
            iterations += 1
            scratchpad.hypotheses.append(
                Hypothesis(
                    text="Graph or multi-graph stack likely needed for temporal/causal workloads",
                    confidence=0.65,
                )
            )

        return iterations

    def _run_agentic_loop(
        self,
        inputs: ProfilingInput,
        scratchpad: InvestigationScratchpad,
        api_key: str,
    ) -> int:
        base_url = os.environ.get("MEMBRANE_LLM_BASE_URL")
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

        system = (
            "You are a Membrane profiling researcher. Analyze the customer's codebase and/or "
            "product surface while actively querying the memory-architecture knowledge base. "
            "Call mak_search whenever you need evidence. Compare patterns when choosing between "
            "approaches. Think step by step; do not finalize until you have enough evidence."
        )
        user = json.dumps(
            {
                "codebase_bundle_summary": inputs.codebase_bundle,
                "product_bundle_summary": inputs.product_bundle,
                "stated_constraints": inputs.stated_constraints,
                "scratchpad": scratchpad.to_context_blob(),
            },
            default=str,
        )[:20000]

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        iterations = 0

        for _ in range(self.max_iterations):
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.mak_tools.tool_specs(),
                tool_choice="auto",
            )
            message = response.choices[0].message
            iterations += 1

            if not message.tool_calls:
                if message.content:
                    scratchpad.notes.append(message.content[:2000])
                break

            messages.append(message.model_dump())
            for call in message.tool_calls:
                fn = call.function
                args = json.loads(fn.arguments or "{}")
                result = self.mak_tools.execute(fn.name, args)
                chunks = self.mak_tools.result_to_chunks(fn.name, result)
                scratchpad.add_chunks(chunks)
                scratchpad.record_tool(
                    agent="profiling_orchestrator",
                    tool=fn.name,
                    arguments=args,
                    summary=str(result)[:200],
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str)[:8000],
                    }
                )

        return iterations

    def _synthesize_profile(
        self,
        inputs: ProfilingInput,
        scratchpad: InvestigationScratchpad,
    ) -> ProfileDraft:
        signals = " ".join(scratchpad.codebase_signals + scratchpad.product_signals).lower()
        memory_needs: list[str] = []
        query_patterns: list[str] = []

        if any(k in signals for k in ("temporal", "timeline", "incident", "alert")):
            memory_needs.extend(["temporal", "entity"])
            query_patterns.append("temporal_reasoning")
        if any(k in signals for k in ("causal", "root cause")):
            memory_needs.append("causal")
            query_patterns.append("causal_chains")
        if any(k in signals for k in ("audit", "compliance")):
            memory_needs.append("audit")
            query_patterns.append("audit_provenance")
        if not memory_needs:
            memory_needs = ["semantic"]
            query_patterns = ["similarity_lookup"]

        product_type = "cybersecurity_agent" if "security" in signals or "soc" in signals else "unknown"
        if inputs.product_bundle and inputs.product_bundle.get("product_type"):
            product_type = inputs.product_bundle["product_type"]

        return ProfileDraft(
            product_type=product_type,
            memory_needs=sorted(set(memory_needs)),
            query_patterns=sorted(set(query_patterns)),
            constraints=inputs.stated_constraints or {},
            mak_evidence_ids=scratchpad.mak_source_ids(),
            tool_call_count=len(scratchpad.tool_calls),
            confidence=0.7 if scratchpad.mak_chunks else 0.4,
            rationale=scratchpad.notes[-1] if scratchpad.notes else "Heuristic profile from bundles + MAK tool loop",
        )
