"""Agent-callable tools over MAK — search, patterns, compare, source sections."""

from __future__ import annotations

import json
from typing import Any

from membrane.knowledge.client import MAKClient
from membrane.knowledge.comparison import ComparisonContext
from membrane.knowledge.models.knowledge import EvidenceChunk


MAK_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "mak_search",
            "description": (
                "Semantic search over the memory-architecture knowledge base "
                "(papers, catalog patterns, extracted chunks). Call whenever you need "
                "evidence while analyzing a product or codebase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional taxonomy tags to bias results",
                    },
                    "limit": {"type": "integer", "default": 8},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mak_get_pattern",
            "description": "Load a structured catalog pattern by id (e.g. graphiti, magma_multigraph).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_id": {"type": "string"},
                },
                "required": ["pattern_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mak_compare",
            "description": (
                "Compare 2-5 catalog patterns side-by-side and pull relevant evidence chunks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 5,
                    },
                    "focus": {
                        "type": "string",
                        "description": "What to compare (e.g. temporal reasoning, on-prem deploy)",
                    },
                },
                "required": ["pattern_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mak_get_source_section",
            "description": "Read a section from an ingested source document (paper, README).",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "section_path": {
                        "type": "string",
                        "description": "Section path slug or empty for abstract/title",
                    },
                },
                "required": ["source_id"],
            },
        },
    },
]


class MAKToolHandler:
    """Execute MAK tools for agentic retrieval loops."""

    def __init__(self, client: MAKClient | None = None) -> None:
        self.client = client or MAKClient()

    @staticmethod
    def tool_specs() -> list[dict[str, Any]]:
        return MAK_TOOL_SPECS

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "mak_search":
            return self._mak_search(**arguments)
        if tool_name == "mak_get_pattern":
            return self._mak_get_pattern(**arguments)
        if tool_name == "mak_compare":
            return self._mak_compare(**arguments)
        if tool_name == "mak_get_source_section":
            return self._mak_get_source_section(**arguments)
        raise ValueError(f"Unknown MAK tool: {tool_name}")

    def _mak_search(self, query: str, tags: list[str] | None = None, limit: int = 8) -> dict[str, Any]:
        results = self.client.search(query, tags=tags, limit=limit)
        return {
            "query": query,
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "source_id": r.source_id,
                    "section_path": r.section_path,
                    "chunk_type": r.chunk_type,
                    "pattern_id": r.pattern_id,
                    "score": r.score,
                    "text": r.text[:1500],
                }
                for r in results
            ],
        }

    def _mak_get_pattern(self, pattern_id: str) -> dict[str, Any]:
        pattern = self.client.get_pattern(pattern_id)
        return json.loads(pattern.model_dump_json())

    def _mak_compare(
        self,
        pattern_ids: list[str],
        focus: str | None = None,
    ) -> dict[str, Any]:
        ctx = self.client.compare(pattern_ids, focus=focus)
        return json.loads(ctx.model_dump_json())

    def _mak_get_source_section(self, source_id: str, section_path: str = "") -> dict[str, Any]:
        text = self.client.get_source_section(source_id, section_path=section_path)
        return {"source_id": source_id, "section_path": section_path, "text": text}

    def result_to_chunks(self, tool_name: str, result: dict[str, Any]) -> list[EvidenceChunk]:
        """Normalize tool results into evidence chunks for the scratchpad."""
        if tool_name == "mak_search":
            return [
                EvidenceChunk(
                    id=r["chunk_id"],
                    source_id=r["source_id"],
                    chunk_type=r.get("chunk_type", "section"),
                    section_path=r.get("section_path", ""),
                    text=r["text"],
                    pattern_id=r.get("pattern_id"),
                )
                for r in result.get("results", [])
            ]
        if tool_name == "mak_compare":
            raw = result.get("evidence_chunks", [])
            return [EvidenceChunk.model_validate(c) if isinstance(c, dict) else c for c in raw]
        return []
