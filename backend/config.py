import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ollama_url: str
    model_name: str
    embed_model: str
    chroma_path: str
    docs_path: str
    max_results: int
    confidence_threshold: float
    debug: bool

    @classmethod
    def from_env(cls):
        return cls(
            ollama_url=os.getenv(
                "OLLAMA_URL", "http://ollama:11434"
            ).rstrip("/"),
            model_name=os.getenv(
                "MODEL_NAME", "llama3.2:1b"
            ),
            embed_model=os.getenv(
                "EMBED_MODEL", "nomic-embed-text"
            ),
            chroma_path=os.getenv(
                "CHROMA_PATH", "/app/chroma_data"
            ),
            docs_path=os.getenv(
                "DOCS_PATH", "/app/docs"
            ),
            max_results=max(
                1, int(os.getenv("MAX_RESULTS", "5"))
            ),
            confidence_threshold=float(
                os.getenv("CONFIDENCE_THRESHOLD", "0.75")
            ),
            debug=os.getenv(
                "DEBUG", "false"
            ).lower() in ("true", "1", "yes"),
        )


settings = Settings.from_env()

if not 0 <= settings.confidence_threshold <= 1:
    raise ValueError(
        "CONFIDENCE_THRESHOLD must be between 0 and 1."
    )