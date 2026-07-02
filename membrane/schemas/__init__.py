"""Shared contracts between Part A and Part B."""

from membrane.schemas.hybrid import (
    ArchitectureCandidate,
    HybridArchitecture,
    HybridComponent,
    MonolithicCandidate,
    RouterRule,
    RouterSpec,
)
from membrane.schemas.manifest import DeploymentManifest, HybridDeployment, ManifestComponent
from membrane.schemas.recommendation import CandidateScore, RecommendationReport, WinnerRef

__all__ = [
    "ArchitectureCandidate",
    "HybridArchitecture",
    "HybridComponent",
    "MonolithicCandidate",
    "RouterRule",
    "RouterSpec",
    "DeploymentManifest",
    "HybridDeployment",
    "ManifestComponent",
    "CandidateScore",
    "RecommendationReport",
    "WinnerRef",
]
