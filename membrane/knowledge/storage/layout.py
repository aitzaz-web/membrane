"""Storage paths under .membrane/knowledge/."""

from __future__ import annotations

import json
from pathlib import Path

from membrane.knowledge.models.extraction import ArchitectureExtraction
from membrane.knowledge.models.knowledge import EvidenceChunk, SourceDocument


class KnowledgeLayout:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(".membrane/knowledge")

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def corpus_documents_dir(self) -> Path:
        return self.root / "corpus" / "documents"

    @property
    def corpus_chunks_dir(self) -> Path:
        return self.root / "corpus" / "chunks"

    @property
    def review_pending_dir(self) -> Path:
        return self.root / "review" / "pending"

    @property
    def review_approved_dir(self) -> Path:
        return self.root / "review" / "approved"

    @property
    def review_rejected_dir(self) -> Path:
        return self.root / "review" / "rejected"

    @property
    def index_dir(self) -> Path:
        return self.root / "index"

    @property
    def vectors_db(self) -> Path:
        return self.index_dir / "vectors.db"

    def ensure_dirs(self) -> None:
        for d in [
            self.raw_dir,
            self.corpus_documents_dir,
            self.corpus_chunks_dir,
            self.review_pending_dir,
            self.review_approved_dir,
            self.review_rejected_dir,
            self.index_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def raw_path(self, source_id: str, ext: str) -> Path:
        return self.raw_dir / f"{source_id}.{ext}"

    def document_path(self, source_id: str) -> Path:
        return self.corpus_documents_dir / f"{source_id}.json"

    def chunks_path(self, source_id: str) -> Path:
        return self.corpus_chunks_dir / f"{source_id}.json"

    def save_document(self, doc: SourceDocument) -> Path:
        self.corpus_documents_dir.mkdir(parents=True, exist_ok=True)
        path = self.document_path(doc.source.source_id)
        path.write_text(doc.model_dump_json(indent=2))
        return path

    def load_document(self, source_id: str) -> SourceDocument | None:
        path = self.document_path(source_id)
        if not path.exists():
            return None
        return SourceDocument.model_validate_json(path.read_text())

    def save_chunks(self, source_id: str, chunks: list[EvidenceChunk]) -> Path:
        self.corpus_chunks_dir.mkdir(parents=True, exist_ok=True)
        path = self.chunks_path(source_id)
        path.write_text(json.dumps([c.model_dump(mode="json") for c in chunks], indent=2))
        return path

    def load_chunks(self, source_id: str) -> list[EvidenceChunk]:
        path = self.chunks_path(source_id)
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return [EvidenceChunk.model_validate(c) for c in data]

    def list_document_ids(self) -> list[str]:
        if not self.corpus_documents_dir.exists():
            return []
        return sorted(p.stem for p in self.corpus_documents_dir.glob("*.json"))

    def list_all_chunks(self) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        if not self.corpus_chunks_dir.exists():
            return chunks
        for path in self.corpus_chunks_dir.glob("*.json"):
            chunks.extend(self.load_chunks(path.stem))
        return chunks

    def review_path(self, extraction_id: str, status: str = "pending") -> Path:
        dirs = {
            "pending": self.review_pending_dir,
            "approved": self.review_approved_dir,
            "rejected": self.review_rejected_dir,
        }
        return dirs[status] / f"{extraction_id}.json"

    def save_review_item(self, item: dict) -> Path:
        self.review_pending_dir.mkdir(parents=True, exist_ok=True)
        path = self.review_path(item["extraction_id"], "pending")
        path.write_text(json.dumps(item, indent=2, default=str))
        return path

    def load_review_item(self, extraction_id: str, status: str = "pending") -> dict | None:
        path = self.review_path(extraction_id, status)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_pending_reviews(self) -> list[dict]:
        if not self.review_pending_dir.exists():
            return []
        items = []
        for path in sorted(self.review_pending_dir.glob("*.json")):
            items.append(json.loads(path.read_text()))
        return items

    def move_review(self, extraction_id: str, to_status: str) -> Path:
        from_path = self.review_path(extraction_id, "pending")
        to_path = self.review_path(extraction_id, to_status)
        to_path.parent.mkdir(parents=True, exist_ok=True)
        if from_path.exists():
            from_path.rename(to_path)
        return to_path
