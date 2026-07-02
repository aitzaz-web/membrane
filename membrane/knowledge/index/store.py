"""sqlite-vec vector store for evidence chunks and patterns."""

from __future__ import annotations

import json
import sqlite3
import struct
from dataclasses import dataclass

import sqlite_vec

from membrane.catalog.loader import load_all_patterns
from membrane.knowledge.index.embedder import embed_text, embed_texts, get_model_name
from membrane.knowledge.models.knowledge import EvidenceChunk
from membrane.knowledge.storage.layout import KnowledgeLayout


def _serialize_f32(vector) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


@dataclass
class SearchResult:
    chunk_id: str
    source_id: str
    chunk_type: str
    section_path: str
    text: str
    score: float
    pattern_id: str | None = None


class VectorIndex:
    def __init__(self, db_path=None, layout: KnowledgeLayout | None = None) -> None:
        self.layout = layout or KnowledgeLayout()
        self.db_path = db_path or self.layout.vectors_db
        self.dim: int | None = None
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.layout.index_dir.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._init_schema()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_schema(self) -> None:
        assert self._conn
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                chunk_type TEXT NOT NULL,
                section_path TEXT,
                text TEXT NOT NULL,
                pattern_id TEXT,
                metadata TEXT
            )
            """
        )
        self._conn.commit()

    def _ensure_vec_table(self, dim: int) -> None:
        assert self._conn
        self.dim = dim
        self._conn.execute("DROP TABLE IF EXISTS chunk_vectors")
        self._conn.execute(
            f"""
            CREATE VIRTUAL TABLE chunk_vectors USING vec0(
                chunk_id TEXT PRIMARY KEY,
                embedding FLOAT[{dim}]
            )
            """
        )
        self._conn.commit()

    def rebuild(self) -> int:
        chunks = self.layout.list_all_chunks()
        patterns = load_all_patterns()

        rows: list[dict] = []
        for chunk in chunks:
            rows.append(
                {
                    "chunk_id": chunk.id,
                    "source_id": chunk.source_id,
                    "chunk_type": chunk.chunk_type,
                    "section_path": chunk.section_path,
                    "text": chunk.text,
                    "pattern_id": chunk.pattern_id,
                    "embedding_text": chunk.embedding_text(),
                }
            )

        for pattern in patterns:
            chunk_id = f"pattern_{pattern.id}"
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "source_id": f"catalog_{pattern.id}",
                    "chunk_type": "pattern",
                    "section_path": pattern.id,
                    "text": pattern.embedding_text(),
                    "pattern_id": pattern.id,
                    "embedding_text": pattern.embedding_text(),
                }
            )

        if not rows:
            conn = self.connect()
            conn.execute("DELETE FROM chunks")
            conn.commit()
            return 0

        texts = [r["embedding_text"] for r in rows]
        vectors = embed_texts(texts)
        dim = vectors.shape[1]

        conn = self.connect()
        conn.execute("DELETE FROM chunks")
        try:
            conn.execute("DELETE FROM chunk_vectors")
        except sqlite3.OperationalError:
            pass
        self._ensure_vec_table(dim)

        seen_ids: set[str] = set()
        for row, vec in zip(rows, vectors):
            if row["chunk_id"] in seen_ids:
                continue
            seen_ids.add(row["chunk_id"])
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, source_id, chunk_type, section_path, text, pattern_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["chunk_id"],
                    row["source_id"],
                    row["chunk_type"],
                    row["section_path"],
                    row["text"],
                    row["pattern_id"],
                    json.dumps({"model": get_model_name()}),
                ),
            )
            conn.execute(
                "INSERT INTO chunk_vectors (chunk_id, embedding) VALUES (?, ?)",
                (row["chunk_id"], _serialize_f32(vec.tolist())),
            )

        conn.commit()
        return len(rows)

    def search(self, query: str, limit: int = 10, tags: list[str] | None = None) -> list[SearchResult]:
        conn = self.connect()
        if self.dim is None:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='chunk_vectors'"
            ).fetchone()
            if not row:
                return []
            import re

            match = re.search(r"FLOAT\[(\d+)\]", row[0])
            if match:
                self.dim = int(match.group(1))

        if self.dim is None:
            return []

        query_vec = embed_text(query)
        serialized = _serialize_f32(query_vec.tolist())

        sql = """
            SELECT c.chunk_id, c.source_id, c.chunk_type, c.section_path, c.text, c.pattern_id,
                   v.distance
            FROM chunk_vectors v
            JOIN chunks c ON c.chunk_id = v.chunk_id
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY v.distance
        """
        results: list[SearchResult] = []
        try:
            rows = conn.execute(sql, (serialized, limit * 2)).fetchall()
        except sqlite3.OperationalError:
            return []

        for row in rows:
            score = 1.0 - float(row[6]) if row[6] is not None else 0.0
            text = row[4]
            if tags and not any(t.lower() in text.lower() for t in tags):
                continue
            results.append(
                SearchResult(
                    chunk_id=row[0],
                    source_id=row[1],
                    chunk_type=row[2],
                    section_path=row[3] or "",
                    text=text,
                    pattern_id=row[5],
                    score=score,
                )
            )
            if len(results) >= limit:
                break
        return results

    def count(self) -> int:
        conn = self.connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0
