"""Service configuration shared by pipeline commands, independent of the API."""

import os
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineSettings(BaseSettings):
    """Read the same local service endpoints as the Compose development stack."""

    hapi_fhir_url: str = "http://localhost:58080/fhir"
    neo4j_uri: str = "bolt://localhost:57687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 55432
    postgres_db: str = "fhirgraph"
    postgres_user: str = "fhirgraph"
    postgres_password: str | None = None

    def __init__(self, **values: Any) -> None:
        if "_env_file" not in values:
            values["_env_file"] = os.environ.get("FHIRGRAPH_ENV_FILE", ".env")
        super().__init__(**values)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
