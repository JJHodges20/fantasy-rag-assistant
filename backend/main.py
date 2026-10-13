"""FastAPI endpoints for the Fantasy Archives containerized RAG backend."""

from __future__ import annotations

import chromadb
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import settings
from ingest import IndexManager
import rag


app = FastAPI(
    title="The Fantasy Archives API",
    version="3.0.0",
    debug=settings.debug,
)

chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
index_manager = IndexManager(chroma_client, settings.chroma_path)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    series: str = "all"  # Optional for existing clients.


def ollama_post(endpoint: str, payload: dict) -> dict:
    """Make an Ollama request and translate connection failures to HTTP 503."""
    try:
        response = requests.post(
            f"{settings.ollama_url}{endpoint}",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama request failed: {exc}",
        ) from exc


@app.get("/")
def root():
    """Return application and model information."""
    return {
        "message": "The Fantasy Archives API is running",
        "model": settings.model_name,
        "embedding_model": settings.embed_model,
    }


@app.get("/health")
def health():
    """Return connection status and count of currently indexed chunks."""
    ollama_connected = False
    installed_models = []
    try:
        response = requests.get(f"{settings.ollama_url}/api/tags", timeout=5)
        response.raise_for_status()
        ollama_connected = True
        installed_models = [
            model["name"] for model in response.json().get("models", [])
        ]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        pass

    return {
        "status": "healthy",
        "ollama": "connected" if ollama_connected else "unavailable",
        "model": settings.model_name,
        "embedding_model": settings.embed_model,
        "installed_models": installed_models,
        "documents": index_manager.active_collection().count(),
    }


@app.get("/stats")
def stats():
    """Show indexed chunks, file counts, and counts for each universe."""
    return {
        **index_manager.stats(),
        "chat_model": settings.model_name,
        "embedding_model": settings.embed_model,
    }


@app.post("/ingest")
def ingest_documents():
    """Safely replace the knowledge index with the five-series corpus."""
    try:
        return index_manager.index_documents(
            settings.docs_path,
            embed=lambda texts: rag.embed_texts(
                texts, settings.embed_model, ollama_post
            ),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    # HTTPException(503) from ollama_post is intentionally propagated.


@app.post("/ask")
def ask_question(request: QuestionRequest):
    """Answer a question using only matching indexed source chunks."""
    try:
        return rag.ask(
            question=request.question,
            series=request.series,
            index_manager=index_manager,
            settings=settings,
            ollama_post=ollama_post,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
