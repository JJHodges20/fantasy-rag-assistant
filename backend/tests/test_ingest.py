"""Offline tests for document discovery and safe ChromaDB index switching."""

import json
from pathlib import Path

import pytest

from ingest import IndexManager, discover_documents, prepare_chunks, split_text


class FakeCollection:
    def __init__(self, name, fail_upsert=False):
        self.name = name
        self.entries = {}
        self.fail_upsert = fail_upsert

    def count(self):
        return len(self.entries)

    def upsert(self, ids, documents, metadatas, embeddings):
        if self.fail_upsert:
            raise RuntimeError("Disk full")
        for i, text, metadata, embedding in zip(
            ids, documents, metadatas, embeddings
        ):
            self.entries[i] = (text, metadata, embedding)

    def get(self, include=None):
        return {"metadatas": [record[1] for record in self.entries.values()]}


class FakeClient:
    def __init__(self):
        self.collections = {}
        self.fail_new_collection = False

    def get_or_create_collection(self, name, metadata=None):
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]

    def create_collection(self, name, metadata=None):
        assert name not in self.collections
        collection = FakeCollection(name, fail_upsert=self.fail_new_collection)
        self.collections[name] = collection
        return collection

    def delete_collection(self, name):
        del self.collections[name]

    def list_collections(self):
        return list(self.collections.values())


def make_docs(root: Path):
    folder = root / "mistborn"
    folder.mkdir(parents=True)
    (folder / "magic_systems.txt").write_text(
        "TITLE: Metallic Arts\n\n" + "Allomancy draws on external power. " * 40,
        encoding="utf-8",
    )
    (root / "narnia").mkdir()
    (root / "narnia" / "world_and_history.txt").write_text(
        "TITLE: Narnia\n\nAslan sang the world into existence.",
        encoding="utf-8",
    )
    (root / "sample.txt").write_text("Old placeholder", encoding="utf-8")


def fake_embed(texts):
    return [[float(len(text)), 0.1, 0.2] for text in texts]


def test_recursive_discovery_skips_old_sample(tmp_path):
    make_docs(tmp_path)
    files = discover_documents(tmp_path)
    assert [path.relative_to(tmp_path).as_posix() for path in files] == [
        "mistborn/magic_systems.txt", "narnia/world_and_history.txt"
    ]
    records, source_count = prepare_chunks(tmp_path)
    assert source_count == 2
    assert all(record["metadata"]["series"] in {"mistborn", "narnia"} for record in records)
    assert all("/" in record["metadata"]["source"] for record in records)
    assert all(len(record["text"]) <= 1000 for record in records)


def test_chunking_has_overlap_and_is_deterministic():
    text = "Allomancy " * 350
    one = split_text(text, chunk_size=350, overlap=60)
    two = split_text(text, chunk_size=350, overlap=60)
    assert one == two
    assert len(one) > 1
    assert all(0 < len(chunk) <= 350 for chunk in one)
    assert "Allomancy" in one[1]


def test_successful_indexing_updates_pointer_after_verification(tmp_path):
    docs = tmp_path / "docs"
    make_docs(docs)
    client = FakeClient()
    manager = IndexManager(client, tmp_path / "chroma")
    previous = manager.active_collection()
    previous.upsert(["old"], ["old data"], [{"source": "old"}], [[0.1]])

    result = manager.index_documents(docs, fake_embed, embed_batch_size=2)
    assert result["files"] == 2
    assert result["chunks"] > 1
    assert manager.active_name().startswith("fantasy_docs_")
    assert manager.active_collection().count() == result["chunks"]
    assert previous.count() == 1  # The previous index was preserved.
    assert manager.stats()["source_files"] == 2
    assert manager.stats()["series_counts"]["narnia"] >= 1

    # A second manager instance sees the active pointer on disk.
    reloaded = IndexManager(client, tmp_path / "chroma")
    assert reloaded.active_name() == manager.active_name()


def test_embedding_failure_does_not_switch_index(tmp_path):
    docs = tmp_path / "docs"
    make_docs(docs)
    client = FakeClient()
    manager = IndexManager(client, tmp_path / "chroma")
    assert manager.active_name() == "documents"

    def broken_embed(texts):
        raise RuntimeError("Ollama is offline")

    with pytest.raises(RuntimeError, match="offline"):
        manager.index_documents(docs, broken_embed)
    assert manager.active_name() == "documents"
    assert list(client.collections) == []  # No staging collection created.


def test_storage_failure_preserves_previous_collection(tmp_path):
    docs = tmp_path / "docs"
    make_docs(docs)
    client = FakeClient()
    manager = IndexManager(client, tmp_path / "chroma")
    client.fail_new_collection = True

    with pytest.raises(RuntimeError, match="Disk full"):
        manager.index_documents(docs, fake_embed)
    assert manager.active_name() == "documents"
    assert not any(name.startswith("fantasy_docs_") for name in client.collections)
