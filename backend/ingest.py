"""Discover, chunk and safely index the Fantasy Archives document corpus.

The active Chroma collection is recorded in a small JSON file inside the
persistent Chroma volume. A replacement collection becomes active only after
all of its embeddings have been stored and verified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from collections import Counter
from pathlib import Path
from typing import Callable


SERIES = (
    "lord_of_the_rings",
    "red_rising",
    "mistborn",
    "harry_potter",
    "narnia",
)
COLLECTION_METADATA = {"hnsw:space": "cosine"}
ACTIVE_INDEX_FILE = "active_index.json"
INDEX_PREFIX = "fantasy_docs_"


def split_text(text: str, chunk_size: int = 1000, overlap: int = 120) -> list[str]:
    """Split text into overlapping, mostly word/paragraph-aligned chunks."""
    if chunk_size < 100 or overlap < 0 or overlap >= chunk_size // 2:
        raise ValueError("Use chunk_size >= 100 and overlap < half the chunk size.")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    chunks = []
    start = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            # Prefer paragraph boundaries, then sentence/word boundaries.
            minimum = start + chunk_size // 2
            for separator in ("\n\n", ". ", " "):
                boundary = normalized.rfind(separator, minimum, end)
                if boundary != -1:
                    end = boundary + len(separator)
                    break

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break

        next_start = max(start + 1, end - overlap)
        # Avoid beginning in the middle of a word.
        while next_start < end and not normalized[next_start - 1].isspace():
            next_start += 1
        start = next_start

    return chunks


def discover_documents(docs_path: str | Path) -> list[Path]:
    """Find .txt files in the five series folders, recursively and in order."""
    root = Path(docs_path)
    if not root.is_dir():
        raise FileNotFoundError(f"Document directory not found: {root}")

    paths = [
        path for path in root.rglob("*.txt")
        if path.is_file() and path.relative_to(root).parts[0] in SERIES
    ]
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def prepare_chunks(docs_path: str | Path) -> tuple[list[dict], int]:
    """Return source/metadata/ID records and the number of source files."""
    root = Path(docs_path)
    files = discover_documents(root)
    if not files:
        raise ValueError(
            "No fantasy .txt documents found in the five series folders. "
            "Check backend/docs/ and remove the old sample.txt."
        )

    records = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8-sig").strip()
        if not content:
            raise ValueError(f"The document is empty: {relative}")

        for index, chunk in enumerate(split_text(content)):
            stable_id = hashlib.sha256(
                f"{relative}:{index}:{chunk}".encode("utf-8")
            ).hexdigest()
            records.append({
                "id": stable_id,
                "text": chunk,
                "metadata": {
                    "source": relative,
                    "series": path.relative_to(root).parts[0],
                    "chunk_index": index,
                    "spoiler_level": "full",
                },
            })

    if not records:
        raise ValueError("No indexable text was found in the documents.")
    return records, len(files)


class IndexManager:
    """Track the live index and switch to newly built indexes safely."""

    def __init__(self, client, chroma_path: str | Path):
        self.client = client
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.pointer = self.chroma_path / ACTIVE_INDEX_FILE
        self._ingest_lock = threading.Lock()

    def active_name(self) -> str:
        """Return the persisted active collection (legacy name if absent)."""
        if not self.pointer.exists():
            return "documents"
        data = json.loads(self.pointer.read_text(encoding="utf-8"))
        name = data.get("collection", "")
        if name != "documents" and not (
            isinstance(name, str) and name.startswith(INDEX_PREFIX)
        ):
            raise ValueError("The active index pointer contains an invalid name.")
        return name

    def active_collection(self):
        """Get the collection currently used for questions and statistics."""
        name = self.active_name()
        return self.client.get_or_create_collection(
            name=name, metadata=COLLECTION_METADATA
        )

    def stats(self) -> dict:
        """Count indexed chunks, unique source files, and chunks per series."""
        collection = self.active_collection()
        count = collection.count()
        series_counts = {series: 0 for series in SERIES}
        sources = set()
        if count:
            result = collection.get(include=["metadatas"])
            for metadata in result.get("metadatas", []):
                if not metadata:
                    continue
                sources.add(metadata.get("source", ""))
                series = metadata.get("series", "")
                if series in series_counts:
                    series_counts[series] += 1
        return {
            "document_count": count,  # Indexed chunks (original API field)
            "source_files": len(sources),
            "series_counts": series_counts,
        }

    def index_documents(
        self,
        docs_path: str | Path,
        embed: Callable[[list[str]], list[list[float]]],
        embed_batch_size: int = 12,
        write_batch_size: int = 50,
    ) -> dict:
        """Build a complete staging index; activate it only after verification.

        If embedding or storage fails, the current collection remains active.
        The prior generation is retained for rollback / in-flight queries.
        """
        with self._ingest_lock:
            records, file_count = prepare_chunks(docs_path)
            embeddings = []
            for start in range(0, len(records), embed_batch_size):
                batch = records[start:start + embed_batch_size]
                vectors = embed([record["text"] for record in batch])
                if len(vectors) != len(batch) or any(not vector for vector in vectors):
                    raise RuntimeError("Ollama returned an invalid number of embeddings.")
                embeddings.extend(vectors)

            vector_size = len(embeddings[0])
            if any(len(vector) != vector_size for vector in embeddings):
                raise RuntimeError("Ollama returned inconsistent embedding dimensions.")

            previous_name = self.active_name()
            staging_name = INDEX_PREFIX + uuid.uuid4().hex[:20]
            staging = self.client.create_collection(
                name=staging_name, metadata=COLLECTION_METADATA
            )
            activated = False
            try:
                for start in range(0, len(records), write_batch_size):
                    batch = records[start:start + write_batch_size]
                    staging.upsert(
                        ids=[record["id"] for record in batch],
                        documents=[record["text"] for record in batch],
                        metadatas=[record["metadata"] for record in batch],
                        embeddings=embeddings[start:start + len(batch)],
                    )

                if staging.count() != len(records):
                    raise RuntimeError("The new ChromaDB index failed count verification.")

                # os.replace is atomic on the same filesystem/volume.
                temporary_pointer = self.pointer.with_suffix(".tmp")
                temporary_pointer.write_text(
                    json.dumps({"collection": staging_name}) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary_pointer, self.pointer)
                activated = True
            finally:
                if not activated:
                    # Never delete the currently active collection on failure.
                    self.client.delete_collection(name=staging_name)

            # Retain the previous generation. Clean older staging indexes;
            # cleanup failures must not turn a successful ingest into an error.
            try:
                for item in self.client.list_collections():
                    name = item if isinstance(item, str) else item.name
                    if name.startswith(INDEX_PREFIX) and name not in {
                        previous_name, staging_name
                    }:
                        self.client.delete_collection(name=name)
            except Exception:
                pass

            return {
                "message": "Documents indexed successfully",
                "files": file_count,
                "chunks": len(records),
                "collection": staging_name,
            }
