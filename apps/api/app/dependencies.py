"""Dependency injection: Neo4j driver and PostgreSQL pool."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import asyncpg
import httpx
from apps.api.app.config import settings
from fastapi import HTTPException
from neo4j import READ_ACCESS, AsyncDriver, AsyncGraphDatabase, AsyncSession


@dataclass(frozen=True)
class DependencyStatus:
    """Result of one bounded dependency probe."""

    ready: bool
    detail: str | None = None


@dataclass(frozen=True)
class DependencyReadiness:
    """Readiness state for every required API dependency."""

    dependencies: dict[str, DependencyStatus]

    @property
    def ready(self) -> bool:
        """Return true only when every required dependency responds."""
        return all(status.ready for status in self.dependencies.values())


class DatabaseConnections:
    """Manages database connections for the application lifespan."""

    def __init__(self) -> None:
        self.neo4j_driver: AsyncDriver | None = None
        self.pg_pool: asyncpg.Pool[asyncpg.Record] | None = None

    async def connect(self) -> None:
        """Establish connections to Neo4j and PostgreSQL."""
        self.neo4j_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify Neo4j connectivity
        try:
            await self.neo4j_driver.verify_connectivity()
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")
            await self.neo4j_driver.close()
            self.neo4j_driver = None

        try:
            self.pg_pool = await asyncpg.create_pool(
                dsn=settings.postgres_dsn,
                min_size=2,
                max_size=10,
            )
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            self.pg_pool = None

    async def readiness(self) -> DependencyReadiness:
        """Probe required dependencies instead of trusting client objects."""
        neo4j, postgres, hapi = await asyncio.gather(
            self._check_neo4j(),
            self._check_postgres(),
            self._check_hapi(),
        )
        return DependencyReadiness(
            dependencies={
                "neo4j": neo4j,
                "postgres": postgres,
                "hapi": hapi,
            }
        )

    async def _check_neo4j(self) -> DependencyStatus:
        if self.neo4j_driver is None:
            return DependencyStatus(ready=False, detail="not connected")

        try:
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                async with self.neo4j_driver.session() as session:
                    result = await session.run("RETURN 1 AS ok")
                    record = await result.single()
                    if record is None or record["ok"] != 1:
                        return DependencyStatus(ready=False, detail="unexpected response")
        except Exception as exc:
            return DependencyStatus(ready=False, detail=type(exc).__name__)
        return DependencyStatus(ready=True)

    async def _check_postgres(self) -> DependencyStatus:
        if self.pg_pool is None:
            return DependencyStatus(ready=False, detail="not connected")

        try:
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                async with self.pg_pool.acquire() as connection:
                    if await connection.fetchval("SELECT 1") != 1:
                        return DependencyStatus(ready=False, detail="unexpected response")
        except Exception as exc:
            return DependencyStatus(ready=False, detail=type(exc).__name__)
        return DependencyStatus(ready=True)

    async def _check_hapi(self) -> DependencyStatus:
        metadata_url = f"{settings.hapi_fhir_url.rstrip('/')}/metadata"
        try:
            timeout = httpx.Timeout(settings.readiness_timeout_seconds)
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(metadata_url)
                    response.raise_for_status()
        except Exception as exc:
            return DependencyStatus(ready=False, detail=type(exc).__name__)
        return DependencyStatus(ready=True)

    async def disconnect(self) -> None:
        """Close all database connections."""
        if self.neo4j_driver:
            await self.neo4j_driver.close()
            self.neo4j_driver = None
        if self.pg_pool:
            await self.pg_pool.close()
            self.pg_pool = None


db = DatabaseConnections()


async def get_neo4j_session() -> AsyncIterator[AsyncSession]:
    """Provide the shared graph session dependency for API reads."""
    if db.neo4j_driver is None:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session(default_access_mode=READ_ACCESS) as session:
        yield session


async def get_pg_pool() -> Any:
    """Provide the shared metadata pool dependency."""
    if db.pg_pool is None:
        raise HTTPException(status_code=503, detail="PostgreSQL not connected")
    return db.pg_pool
