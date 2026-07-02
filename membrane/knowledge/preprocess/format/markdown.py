"""Markdown parsing helpers."""

from __future__ import annotations

import re

from membrane.knowledge.preprocess.raw import RawDocument


def parse_markdown(raw: RawDocument) -> tuple[str, list[tuple[str, str]]]:
    text = raw.content.decode("utf-8", errors="replace")
    sections: list[tuple[str, str]] = []
    current_title = "Introduction"
    current_lines: list[str] = []

    for line in text.splitlines():
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = heading.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))

    return text, sections if sections else [("Body", text)]
