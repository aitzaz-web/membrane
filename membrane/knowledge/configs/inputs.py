"""Ingest input types — discriminated union per source."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ArxivInput(BaseModel):
    type: Literal["arxiv"] = "arxiv"
    arxiv_id: str


class HttpInput(BaseModel):
    type: Literal["http"] = "http"
    url: str


class GitHubReadmeInput(BaseModel):
    type: Literal["github_readme"] = "github_readme"
    repo: str


class DocsCrawlInput(BaseModel):
    type: Literal["docs_site"] = "docs_site"
    base_url: str
    sitemap: str | None = None


class AwesomeListInput(BaseModel):
    type: Literal["awesome_list"] = "awesome_list"
    repo: str


IngestInput = Annotated[
    ArxivInput | HttpInput | GitHubReadmeInput | DocsCrawlInput | AwesomeListInput,
    Field(discriminator="type"),
]
