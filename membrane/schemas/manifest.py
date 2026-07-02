"""Deployment manifest consumed by Part B."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from membrane.schemas.hybrid import RouterSpec


class ManifestComponent(BaseModel):
    id: str
    role: str
    pattern_id: str
    adapter: str
    config: dict[str, Any] = Field(default_factory=dict)


class HybridDeployment(BaseModel):
    type: Literal["hybrid"] = "hybrid"
    components: list[ManifestComponent] = Field(default_factory=list)
    router: RouterSpec = Field(default_factory=RouterSpec)
    unified_api: bool = True


class MonolithicDeployment(BaseModel):
    type: Literal["monolithic"] = "monolithic"
    pattern_id: str
    adapter: str
    components: list[dict[str, str]] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class DeploymentManifest(BaseModel):
    """Machine-readable deploy spec — monolithic or composed stack."""

    id: str
    mode: Literal["local", "cloud"] = "local"
    deployment: HybridDeployment | MonolithicDeployment
    profile_summary: dict[str, Any] = Field(default_factory=dict)
