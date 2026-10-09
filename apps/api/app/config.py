"""FHIRGraph API configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fhirgraph"
    postgres_user: str = "fhirgraph"
    postgres_password: str  # REQUIRED — no default; must be set via env or .env

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str  # REQUIRED — no default; must be set via env or .env

    # HAPI FHIR
    hapi_fhir_url: str = "http://localhost:8080/fhir"

    # Local OpenAI-compatible model server (Ollama by default)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.1"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "info"
    readiness_timeout_seconds: float = 2.0
    cors_origins: str = "http://localhost:4010,http://127.0.0.1:4010"

    @property
    def postgres_dsn(self) -> str:
        """Construct asyncpg connection string."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def allowed_origins(self) -> list[str]:
        """Parse the comma-separated browser origins accepted by CORS."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()  # type: ignore[call-arg]  # Values are loaded from environment variables.
