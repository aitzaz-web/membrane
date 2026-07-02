"""Recommendation output from Part A."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WinnerRef(BaseModel):
    type: Literal["monolithic", "hybrid"]
    id: str
    pattern_id: str | None = None  # set when monolithic
    name: str


class CandidateScore(BaseModel):
    candidate_id: str
    candidate_type: Literal["monolithic", "hybrid"]
    overall: float
    quality: float | None = None
    latency_fit: float | None = None
    privacy_fit: float | None = None
    compliance_fit: float | None = None
    cost_fit: float | None = None
    component_scores: dict[str, float] = Field(default_factory=dict)


class RecommendationReport(BaseModel):
    winner: WinnerRef
    scores: list[CandidateScore] = Field(default_factory=list)
    runner_up_id: str | None = None
    explanation: str = ""
    tradeoffs: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    component_rationale: dict[str, str] = Field(default_factory=dict)
