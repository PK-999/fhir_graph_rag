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

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "info"

    @property
    def postgres_dsn(self) -> str:
        """Construct asyncpg connection string."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
