"""Offline tests for filtering, no-context behavior and citation integrity."""

from types import SimpleNamespace

import pytest

from rag import ask, embed_texts, NO_CONTEXT_ANSWER


class FakeCollection:
    def __init__(self, records, distance=0.1):
        self.records = records
        self.distance = distance
        self.latest_query = None

    def count(self):
        return len(self.records)

    def query(self, **kwargs):
        self.latest_query = kwargs
        records = self.records
        if "where" in kwargs:
            records = [
                row for row in records
                if row[1]["series"] == kwargs["where"]["series"]
            ]
        return {
            "documents": [[row[0] for row in records]],
            "metadatas": [[row[1] for row in records]],
            "distances": [[self.distance for _ in records]],
        }


class FakeManager:
    def __init__(self, collection):
        self.collection = collection

    def active_collection(self):
        return self.collection


SETTINGS = SimpleNamespace(
    embed_model="nomic-embed-text",
    model_name="llama3.2:1b",
    max_results=5,
    confidence_threshold=0.75,
)


def respond(endpoint, payload):
    if endpoint == "/api/embed":
        return {"embeddings": [[1.0, 0.0] for _ in payload["input"]]}
    if endpoint == "/api/chat":
        return {"message": {"content": "Allomancy burns metal. [Source 1]"}}
    raise AssertionError(f"Unexpected endpoint: {endpoint}")


def test_universe_filter_is_applied_inside_vector_query():
    collection = FakeCollection([
        ("Allomancy burns metal.", {
            "series": "mistborn", "source": "mistborn/magic_systems.txt", "chunk_index": 2,
        }),
        ("Aslan made Narnia.", {
            "series": "narnia", "source": "narnia/world_and_history.txt", "chunk_index": 0,
        }),
    ])
    data = ask("What is Allomancy?", "mistborn", FakeManager(collection), SETTINGS, respond)
    assert collection.latest_query["where"] == {"series": "mistborn"}
    assert data["status"] == "answered"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source"] == "mistborn/magic_systems.txt"
    assert data["confidence"] == "high"


def test_no_context_skips_chat_model():
    collection = FakeCollection([
        ("Narnia facts", {"series": "narnia", "source": "narnia/world.txt"}),
    ], distance=0.9)
    called = []

    def fake_post(endpoint, payload):
        called.append(endpoint)
        return respond(endpoint, payload)

    data = ask("What is Narnia?", "all", FakeManager(collection), SETTINGS, fake_post)
    assert data["answer"] == NO_CONTEXT_ANSWER
    assert data["sources"] == []
    assert data["confidence"] == "none"
    assert called == ["/api/embed"]


def test_selected_series_does_not_use_other_universe():
    collection = FakeCollection([
        ("Harry used the wand.", {
            "series": "harry_potter", "source": "harry_potter/spells_and_artifacts.txt",
        }),
    ])
    data = ask("What is a wand?", "narnia", FakeManager(collection), SETTINGS, respond)
    assert data["status"] == "no_context"
    assert not data["sources"]


def test_bad_series_name_is_rejected():
    collection = FakeCollection([("X", {"series": "mistborn"})])
    with pytest.raises(ValueError, match="known series"):
        ask("Question", "star_wars", FakeManager(collection), SETTINGS, respond)


def test_fabricated_citation_id_is_removed():
    collection = FakeCollection([
        ("X", {"series": "mistborn", "source": "mistborn/magic_systems.txt"})
    ])

    def post(endpoint, payload):
        if endpoint == "/api/chat":
            return {"message": {"content": "Magic. [Source 99] [Source 1]"}}
        return respond(endpoint, payload)

    data = ask("Magic?", "all", FakeManager(collection), SETTINGS, post)
    assert "[Source 99]" not in data["answer"]
    assert "[Source 1]" in data["answer"]
