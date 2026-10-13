"""Streamlit chat interface for The Fantasy Archives.

The frontend talks to FastAPI over the Docker Compose internal network.
No model or vector database runs inside the Streamlit container.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")

# The keys are the exact series identifiers expected by backend/rag.py.
SERIES_LABELS = {
    "all": "All universes",
    "lord_of_the_rings": "Lord of the Rings",
    "red_rising": "Red Rising",
    "mistborn": "Mistborn",
    "harry_potter": "Harry Potter",
    "narnia": "Narnia",
}

EXAMPLE_QUESTIONS = {
    "all": "How do Allomancy in Mistborn and the magic of Narnia differ?",
    "lord_of_the_rings": "Why was Frodo unable to destroy the One Ring himself?",
    "red_rising": "How does the Color hierarchy maintain the Society's power?",
    "mistborn": "How do Allomancy, Feruchemy, and Hemalurgy differ?",
    "harry_potter": "Why did the Elder Wand ultimately belong to Harry?",
    "narnia": "What is the difference between the Deep Magic and Deeper Magic?",
}


class BackendError(Exception):
    """Raised when the FastAPI backend fails or cannot be reached."""


def api_request(
    method: str, endpoint: str, *, timeout: int | tuple[int, int] = 20,
    **kwargs: Any,
) -> dict[str, Any]:
    """Request JSON from FastAPI with a readable error on failure."""
    try:
        response = requests.request(
            method,
            f"{BACKEND_URL}{endpoint}",
            timeout=timeout,
            **kwargs,
        )
    except requests.Timeout as exc:
        raise BackendError("The request timed out. The model may still be processing.") from exc
    except requests.RequestException as exc:
        raise BackendError(
            "Cannot connect to the backend. Check 'docker compose ps' and backend logs."
        ) from exc

    if not response.ok:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError, TypeError):
            detail = None
        raise BackendError(str(detail or f"Backend returned HTTP {response.status_code}."))

    try:
        payload = response.json()
    except ValueError as exc:
        raise BackendError("The backend returned an invalid JSON response.") from exc
    if not isinstance(payload, dict):
        raise BackendError("The backend returned an unexpected response format.")
    return payload


def ensure_session_state() -> None:
    """Initialize separate in-memory conversations for each universe."""
    if "conversations" not in st.session_state:
        st.session_state["conversations"] = {
            series: [] for series in SERIES_LABELS
        }


def render_sources(sources: Any) -> None:
    """Show structured citations attached to a single assistant response."""
    if not isinstance(sources, list) or not sources:
        return

    with st.expander(f"Sources ({len(sources)})", expanded=False):
        for position, item in enumerate(sources, start=1):
            if not isinstance(item, dict):
                continue
            identifier = str(item.get("id", f"Source {position}"))
            filename = str(item.get("source", "Unknown document"))
            series = str(item.get("series", ""))
            series_label = SERIES_LABELS.get(series, series or "Unknown universe")
            chunk = item.get("chunk_index", "?")
            similarity = item.get("similarity")

            st.write(f"**{identifier}** — `{filename}`")
            details = f"{series_label} · chunk {chunk}"
            if isinstance(similarity, (int, float)) and not isinstance(similarity, bool):
                details += f" · cosine similarity {similarity:.3f}"
            st.caption(details)


def render_history(messages: list[dict[str, Any]]) -> None:
    """Render this universe's user and assistant messages."""
    for message in messages:
        role = message.get("role", "assistant")
        with st.chat_message(role, avatar="📚" if role == "assistant" else None):
            if message.get("error"):
                st.error(str(message.get("content", "Request failed.")))
                continue

            st.markdown(str(message.get("content", "")))
            if role == "assistant":
                confidence = message.get("confidence")
                if confidence and confidence != "none":
                    st.caption(
                        f"Retrieval strength: {str(confidence).capitalize()} "
                        "(not a factual-accuracy guarantee)"
                    )
                render_sources(message.get("sources", []))


def show_sidebar() -> tuple[str, bool, bool]:
    """Render controls and return (selected series, backend online, has index)."""
    st.sidebar.title("📚 The Fantasy Archives")
    st.sidebar.caption("Full-series spoilers • Five fictional universes")
    selected_series = st.sidebar.selectbox(
        "Choose a universe",
        options=list(SERIES_LABELS),
        format_func=lambda value: SERIES_LABELS[value],
        key="selected_series",
    )
    st.sidebar.divider()

    if st.sidebar.button("🔄 Re-index Documents", use_container_width=True):
        with st.sidebar:
            with st.spinner("Generating embeddings and updating the index. This may take several minutes..."):
                try:
                    result = api_request("POST", "/ingest", timeout=(10, 900))
                except BackendError as exc:
                    st.error(str(exc))
                else:
                    st.success(
                        f"Indexed {result.get('files', '?')} files "
                        f"into {result.get('chunks', '?')} chunks."
                    )

    st.sidebar.subheader("System status")
    try:
        health = api_request("GET", "/health", timeout=8)
    except BackendError as exc:
        health = None
        st.sidebar.error(f"Backend unavailable: {exc}")
    else:
        st.sidebar.success("FastAPI connected")
        if health.get("ollama") == "connected":
            st.sidebar.success("Ollama connected")
        else:
            st.sidebar.warning("Ollama unavailable")
        st.sidebar.caption(f"Chat model: {health.get('model', 'unknown')}")
        st.sidebar.caption(
            f"Embedding model: {health.get('embedding_model', 'unknown')}"
        )

        installed = health.get("installed_models", [])
        if isinstance(installed, list):
            required = [health.get("model"), health.get("embedding_model")]
            missing = [
                model for model in required
                if isinstance(model, str) and model
                and not any(
                    installed_name == model
                    or (":" not in model and installed_name.split(":")[0] == model)
                    for installed_name in installed
                    if isinstance(installed_name, str)
                )
            ]
            if health.get("ollama") == "connected" and missing:
                st.sidebar.warning("Model(s) not installed: " + ", ".join(missing))

    try:
        stats = api_request("GET", "/stats", timeout=15) if health else None
    except BackendError as exc:
        stats = None
        st.sidebar.warning(f"Index statistics unavailable: {exc}")

    count = (stats or {}).get("document_count", (health or {}).get("documents", 0))
    count = count if isinstance(count, int) else 0
    source_files = (stats or {}).get("source_files", 0)
    st.sidebar.metric("Indexed chunks", count)
    st.sidebar.metric("Source files", source_files)

    if stats and isinstance(stats.get("series_counts"), dict):
        with st.sidebar.expander("Chunks by universe"):
            for key, label in SERIES_LABELS.items():
                if key != "all":
                    st.write(f"{label}: {stats['series_counts'].get(key, 0)}")

    if st.sidebar.button("Clear this conversation", use_container_width=True):
        st.session_state["conversations"][selected_series] = []
        st.rerun()

    st.sidebar.caption(
        "Chat history is stored in this Streamlit session, not on disk. "
        "The index is stored persistently in Docker."
    )
    return selected_series, health is not None, count > 0


def main() -> None:
    """Build and run the chat experience."""
    st.set_page_config(
        page_title="The Fantasy Archives",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ensure_session_state()
    selected_series, backend_online, has_index = show_sidebar()

    st.title("The Fantasy Archives")
    st.caption("A document-grounded AI guide to five fantasy universes")
    st.info(
        "**Full spoiler mode:** Answers may reveal major character deaths, "
        "secret identities, and series endings."
    )
    st.subheader(SERIES_LABELS[selected_series])

    history = st.session_state["conversations"][selected_series]
    if not history:
        st.write(
            "Ask a question about characters, magic, events, or history. "
            "The answer will include matching passages from the indexed documents."
        )

    render_history(history)

    can_ask = backend_online and has_index
    if not has_index and backend_online:
        st.warning("No indexed documents found. Use **Re-index Documents** in the sidebar.")
    if not backend_online:
        st.warning("The backend is offline. Start Docker Compose and refresh the page.")

    selected_prompt = None
    if not history:
        selected_prompt = st.button(
            f"Try: {EXAMPLE_QUESTIONS[selected_series]}",
            key=f"example_{selected_series}",
            disabled=not can_ask,
            use_container_width=True,
        )

    typed_prompt = st.chat_input(
        "Ask about the selected universe...",
        key=f"chat_{selected_series}",
        disabled=not can_ask,
        max_chars=4000,
    )
    question = EXAMPLE_QUESTIONS[selected_series] if selected_prompt else typed_prompt
    if not question or not question.strip():
        return

    question = question.strip()
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="📚"):
        with st.spinner("Searching the archives and generating an answer..."):
            try:
                result = api_request(
                    "POST", "/ask", timeout=(10, 240),
                    json={"question": question, "series": selected_series},
                )
            except BackendError as exc:
                error_message = f"Unable to answer this question: {exc}"
                st.error(error_message)
                history.append({"role": "assistant", "content": error_message, "error": True})
            else:
                answer = str(result.get("answer") or "No answer was returned.")
                confidence = result.get("confidence", "none")
                sources = result.get("sources", [])
                st.markdown(answer)
                if confidence and confidence != "none":
                    st.caption(
                        f"Retrieval strength: {str(confidence).capitalize()} "
                        "(not a factual-accuracy guarantee)"
                    )
                render_sources(sources)
                history.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "confidence": confidence,
                    "status": result.get("status", "answered"),
                })


if __name__ == "__main__":
    main()
