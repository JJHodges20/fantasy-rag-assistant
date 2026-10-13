
import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    """Create the API with an isolated test database."""
    test_db = tmp_path_factory.mktemp("chroma")

    # Set the database path before importing main.py.
    import os
    os.environ["CHROMA_PATH"] = str(test_db)

    backend_path = str(
        __import__("pathlib").Path(__file__).resolve().parents[1]
    )
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    app_module = importlib.import_module("main")

    with TestClient(app_module.app) as client:
        yield client, app_module


def test_root_returns_200(api):
    client, _ = api

    response = client.get("/")

    assert response.status_code == 200
    assert "model" in response.json()


def test_health_returns_expected_fields(api, monkeypatch):
    client, app_module = api

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"models": []}

    monkeypatch.setattr(
        app_module.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(),
    )

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["ollama"] == "connected"
    assert "model" in data
    assert "embedding_model" in data
    assert "documents" in data


def test_stats_returns_document_count(api):
    client, _ = api

    response = client.get("/stats")

    assert response.status_code == 200

    data = response.json()

    assert "document_count" in data
    assert isinstance(data["document_count"], int)
    assert data["document_count"] >= 0
