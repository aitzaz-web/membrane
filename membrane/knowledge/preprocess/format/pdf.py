"""PDF text extraction with page boundaries."""

from __future__ import annotations

import re

import fitz  # PyMuPDF

from membrane.knowledge.preprocess.raw import RawDocument


def parse_pdf(raw: RawDocument) -> tuple[str, list[dict]]:
    doc = fitz.open(stream=raw.content, filetype="pdf")
    pages: list[dict] = []
    texts: list[str] = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages.append({"page": i + 1, "text": text})
        texts.append(text)
    full_text = "\n\n".join(texts)
    return full_text, pages


def split_sections(text: str) -> list[tuple[str, str]]:
    """Heuristic section splitter for academic papers."""
    pattern = re.compile(r"\n(?=\d+\.?\s+[A-Z][^\n]{0,80}\n)|\n(?=[A-Z][A-Z\s]{2,}\n)")
    parts = pattern.split(text)
    sections: list[tuple[str, str]] = []
    if not parts:
        return [("Body", text)]

    preamble = parts[0].strip()
    if preamble:
        sections.append(("Preamble", preamble))

    for part in parts[1:]:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n", 1)
        title = lines[0].strip()[:120]
        body = lines[1].strip() if len(lines) > 1 else part
        sections.append((title, body))
    return sections if sections else [("Body", text)]
