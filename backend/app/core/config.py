"""Single source of truth for configuration.

Every tunable in the app is a field on `Settings`. Nothing reads os.environ
directly and no constant is defined at a call site, so there is exactly one
place to look when you want to know what a value is or change it.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> core -> app -> backend. Anchoring the .env path to this file
# instead of the process CWD means `uvicorn` from backend/ and `pytest` from the
# repo root both find the same file.
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        # Real environment variables win over .env, which is what lets Docker
        # and CI inject config without mounting a file.
        # `extra="ignore"` keeps an unrelated variable in the shell (PATH,
        # PYTHONPATH, CI runner noise) from failing app startup.
        extra="ignore",
        case_sensitive=False,
    )

    # --- app -----------------------------------------------------------
    app_name: str = "FastAPI RAG Starter"
    log_level: str = "INFO"
    sql_echo: bool = False

    # --- database ------------------------------------------------------
    # No default. A missing DATABASE_URL should stop the process at import
    # time with a clear pydantic error, not surface as a connection failure
    # on the first request.
    database_url: str
    test_database_url: str = ""

    # --- auth ----------------------------------------------------------
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- cors ----------------------------------------------------------
    # Typed as a plain string because pydantic-settings parses a `list[str]`
    # field as JSON, which would force `["http://a","http://b"]` quoting into
    # .env. Comma-separated is what everyone expects; `cors_origin_list` splits.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- openai --------------------------------------------------------
    # Defaults to empty so the app still boots (and /health still answers)
    # without a key. The RAG routes fail loudly instead; nothing else cares.
    openai_api_key: str = ""

    # --- rag tuning ----------------------------------------------------
    embedding_model: str = "text-embedding-3-small"
    # Must equal the embedding model's output width AND the vector(n) column in
    # migration 0001. These three move together or similarity search breaks.
    embedding_dim: int = 1536
    chat_model: str = "gpt-4o-mini"

    # ~1000 characters is roughly 250 tokens: big enough to hold one complete
    # idea, small enough that the chunk's single embedding is not averaged
    # across several unrelated topics (which is what destroys retrieval).
    chunk_size: int = 1000
    # 15% overlap. A sentence that straddles a boundary otherwise ends up as
    # two half-sentences, neither of which embeds close to the question.
    chunk_overlap: int = 150
    # 4 chunks is ~1000 tokens of context: several chances to contain the
    # answer without burying the model in near-misses it has to argue past.
    top_k: int = 4
    # Cosine distance, so 0 = identical and 2 = opposite. Anything above this is
    # treated as "not actually about the question" and dropped, which is what
    # makes the no-relevant-context path trigger instead of the model being
    # handed noise and inventing an answer from it.
    max_cosine_distance: float = 0.6
    # 5 MB. Upload is synchronous, so this bounds worst-case request time as
    # much as it bounds memory.
    max_upload_bytes: int = 5 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so .env is read once per process rather than per dependency call.

    Also makes Settings a stable singleton, so overriding it in tests overrides
    it everywhere.
    """
    return Settings()
