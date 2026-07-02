"""Compose monolithic and hybrid architecture candidates from profile + catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

from membrane.catalog.loader import ArchitecturePattern, load_all_patterns, load_pattern
from membrane.schemas.hybrid import (
    ArchitectureCandidate,
    HybridArchitecture,
    HybridComponent,
    MonolithicCandidate,
    RouterRule,
    RouterSpec,
    slug_hybrid_id,
)

RECIPES_DIR = Path(__file__).resolve().parent / "recipes"
BASELINE_PATTERN = "vector_rag"


def _covers_need(pattern: ArchitecturePattern, need: str) -> bool:
    return need in pattern.memory_needs_served


def _covers_query(pattern: ArchitecturePattern, query: str) -> bool:
    return query in pattern.query_patterns_served


def _composable_with(existing: list[str], candidate_id: str) -> bool:
    if not existing:
        return True
    for pid in existing:
        try:
            p = load_pattern(pid)
        except FileNotFoundError:
            continue
        if candidate_id in p.composable_with or pid in load_pattern(candidate_id).composable_with:
            return True
        if candidate_id == pid:
            return False
    return True


def greedy_compose_hybrid(
    memory_needs: list[str],
    query_patterns: list[str] | None = None,
    name: str = "Composed stack",
) -> HybridArchitecture:
    """Build a hybrid by covering memory_needs with catalog patterns."""
    patterns = load_all_patterns()
    query_patterns = query_patterns or []

    components: list[HybridComponent] = []
    used_patterns: list[str] = []
    uncovered = list(memory_needs)

    # Always start with vector baseline if semantic is needed or list is empty
    if not uncovered or "semantic" in uncovered:
        baseline = load_pattern(BASELINE_PATTERN)
        components.append(
            HybridComponent(
                role="semantic_retrieval",
                pattern_id=BASELINE_PATTERN,
                serves=[n for n in baseline.memory_needs_served if n in memory_needs] or ["semantic"],
                read_path="similarity",
            )
        )
        used_patterns.append(BASELINE_PATTERN)
        uncovered = [n for n in uncovered if not _covers_need(baseline, n)]

    ranked = sorted(
        patterns,
        key=lambda p: (
            -len([n for n in memory_needs if _covers_need(p, n)]),
            p.id == BASELINE_PATTERN,
        ),
        reverse=False,
    )

    for pattern in ranked:
        if pattern.id in used_patterns:
            continue
        covers = [n for n in uncovered if _covers_need(pattern, n)]
        if not covers:
            continue
        if not _composable_with(used_patterns, pattern.id):
            continue

        role = pattern.id.replace("_", " ")
        components.append(
            HybridComponent(
                role=slug_hybrid_id(role),
                pattern_id=pattern.id,
                serves=covers,
                read_path=pattern.query_patterns_served[0] if pattern.query_patterns_served else None,
            )
        )
        used_patterns.append(pattern.id)
        uncovered = [n for n in uncovered if n not in covers]
        if not uncovered:
            break

    rules: list[RouterRule] = []
    for comp in components:
        pattern = load_pattern(comp.pattern_id)
        when = [q for q in query_patterns if _covers_query(pattern, q)]
        if when:
            rules.append(RouterRule(when=when, use_role=comp.role))
        elif comp.serves:
            rules.append(
                RouterRule(
                    when=[f"memory_need:{s}" for s in comp.serves],
                    use_role=comp.role,
                )
            )

    router = RouterSpec(
        type="query_pattern_routing",
        rules=rules,
        default_role=components[0].role if components else None,
    )

    return HybridArchitecture(
        id=slug_hybrid_id(name),
        name=name,
        base_patterns=used_patterns,
        components=components,
        router=router,
        rationale=f"Greedy coverage of memory needs: {', '.join(memory_needs)}",
    )


def load_recipe(recipe_id: str) -> HybridArchitecture:
    path = RECIPES_DIR / f"{recipe_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Recipe not found: {recipe_id}")
    with path.open() as f:
        data = yaml.safe_load(f)
    data.pop("description", None)
    if "type" in data and data["type"] == "hybrid":
        data.setdefault("id", recipe_id)
    return HybridArchitecture.model_validate(data)


def compose_candidates(
    memory_needs: list[str],
    query_patterns: list[str] | None = None,
    product_type: str | None = None,
    include_baseline: bool = True,
    max_candidates: int = 5,
) -> list[ArchitectureCandidate]:
    """
    Propose eval candidates: monolithic baselines + composed hybrids.

    Output always includes vector_rag monolith and at least one hybrid when
    len(memory_needs) > 1.
    """
    candidates: list[ArchitectureCandidate] = []
    patterns = load_all_patterns()

    if include_baseline:
        baseline = load_pattern(BASELINE_PATTERN)
        candidates.append(
            MonolithicCandidate(
                id=BASELINE_PATTERN,
                name=baseline.name,
                pattern_id=BASELINE_PATTERN,
                rationale="Baseline for comparison",
            )
        )

    # Best single-pattern cover (monolithic)
    best_mono: ArchitecturePattern | None = None
    best_cover = -1
    for p in patterns:
        if p.id == BASELINE_PATTERN:
            continue
        cover = len([n for n in memory_needs if _covers_need(p, n)])
        if cover > best_cover:
            best_cover = cover
            best_mono = p
    if best_mono and best_mono.id not in {c.id for c in candidates}:
        candidates.append(
            MonolithicCandidate(
                id=best_mono.id,
                name=best_mono.name,
                pattern_id=best_mono.id,
                rationale=f"Best single-pattern cover ({best_cover}/{len(memory_needs)} needs)",
            )
        )

    # Product-type recipe template
    if product_type and "cyber" in product_type.lower():
        try:
            recipe = load_recipe("cybersecurity_soc_stack")
            candidates.append(recipe)
        except FileNotFoundError:
            pass

    # Greedy composed hybrid
    if len(memory_needs) > 1:
        hybrid = greedy_compose_hybrid(
            memory_needs=memory_needs,
            query_patterns=query_patterns,
            name="Profile-composed hybrid",
        )
        if hybrid.id not in {c.id for c in candidates}:
            candidates.append(hybrid)

    # MAGMA-style monolith for graph-heavy profiles
    if any(n in memory_needs for n in ("temporal", "causal", "entity")):
        try:
            magma = load_pattern("magma_multigraph")
            if magma.id not in {c.id for c in candidates}:
                candidates.append(
                    MonolithicCandidate(
                        id=magma.id,
                        name=magma.name,
                        pattern_id=magma.id,
                        rationale="Research multi-graph monolith alternative",
                    )
                )
        except FileNotFoundError:
            pass

    return candidates[:max_candidates]


def hybrid_to_manifest(hybrid: HybridArchitecture, mode: str = "local") -> "DeploymentManifest":
    from membrane.schemas.manifest import DeploymentManifest, HybridDeployment, ManifestComponent

    components: list[ManifestComponent] = []
    for comp in hybrid.components:
        pattern = load_pattern(comp.pattern_id)
        adapter = pattern.implementation.adapter if pattern.implementation else f"adapters.{comp.pattern_id}"
        components.append(
            ManifestComponent(
                id=comp.role,
                role=comp.role,
                pattern_id=comp.pattern_id,
                adapter=adapter,
            )
        )

    return DeploymentManifest(
        id=f"deploy_{hybrid.id}",
        mode=mode,  # type: ignore[arg-type]
        deployment=HybridDeployment(
            components=components,
            router=hybrid.router,
            unified_api=True,
        ),
        profile_summary={"memory_needs": [c.serves for c in hybrid.components]},
    )
