"""Tests for paper flow."""

from membrane.knowledge.flows.paper_flow import raw_to_source_document
from membrane.knowledge.preprocess.raw import RawDocument


def test_markdown_to_document():
    raw = RawDocument(
        source_id="test_md",
        source_type="github_readme",
        url="https://example.com",
        title="Test README",
        mime="text/markdown",
        content=b"# Intro\n\nVector memory basics.\n\n## Architecture\n\nUses embeddings.",
    )
    doc, chunks = raw_to_source_document(raw)
    assert doc.title == "Test README"
    assert len(doc.sections) >= 1
    assert len(chunks) >= 1
    assert any(c.chunk_type == "section" for c in chunks)
